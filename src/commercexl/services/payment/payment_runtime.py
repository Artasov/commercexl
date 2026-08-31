from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, PaymentDTO, PaymentOptionsDTO
from commercexl.models import OrderORM, PaymentEvidenceORM, PaymentORM, PaymentOutboxEventORM
from commercexl.order import OrderState
from commercexl.payment import (
    CheckoutAction,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentOptionDTO,
    PaymentState,
    PaymentStateMachine,
    PaymentVerificationResult,
)
from commercexl.services.access import OrderAccessAction
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.idempotency import Idempotency


class PaymentRuntime(BaseRuntime):
    """Владеет payment attempts, переходами, finalization и outbox."""

    event_type = "commerce.payment.updated"

    async def list_payment_options(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> PaymentOptionsDTO:
        """Возвращает только варианты, разрешённые server-side для заказа."""
        order = await self.get_order(session, order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.CREATE_PAYMENT)
        if order.order_state != OrderState.READY_FOR_PAYMENT:
            return PaymentOptionsDTO(options=[])
        if await self._get_active_attempt(session, order.id) is not None:
            return PaymentOptionsDTO(options=[])
        return PaymentOptionsDTO(options=await self._collect_options(session, order, actor))

    async def create_attempt(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            payment_option_id: str,
            actor: CommerceUserActorDTO,
            idempotency_key: str,
    ) -> PaymentDTO:
        """Атомарно создаёт одну server-priced попытку после ownership check."""
        async with session.begin_nested():
            return await self._create_attempt(
                session,
                order_id,
                payment_option_id,
                actor,
                idempotency_key,
            )

    async def _create_attempt(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            payment_option_id: str,
            actor: CommerceUserActorDTO,
            idempotency_key: str,
    ) -> PaymentDTO:
        key = self._normalize_idempotency_key(idempotency_key)
        option_id = str(payment_option_id).strip()
        if not option_id:
            raise self.get_bad_request("Payment option id is required.")
        order = await self.get_order_for_update(session, order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.CREATE_PAYMENT)
        fingerprint = Idempotency.fingerprint(
            {"order_id": str(order.id), "payment_option_id": option_id},
        )

        existing = await self._get_idempotent_attempt(session, actor.id, key)
        if existing is not None:
            self._check_idempotency_fingerprint(existing.idempotency_fingerprint, fingerprint)
            if existing.order_id != order.id:
                raise self.get_conflict("Idempotency key is already used for another payment attempt.")
            action = (
                await self._issue_action(session, existing)
                if existing.payment_state.accepts_checkout_action
                else None
            )
            return await self.create_payment_serializer().serialize_payment(
                session,
                existing,
                action=action,
            )

        if order.order_state == OrderState.EXECUTED:
            raise self.get_conflict("Order is already paid.")
        if order.order_state in {OrderState.CANCELLED, OrderState.REFUNDED}:
            raise self.get_conflict("Order cannot accept a payment attempt.")
        if order.order_state != OrderState.READY_FOR_PAYMENT:
            raise self.get_conflict("Order is not ready for payment.")

        active_attempt = await self._get_active_attempt_for_update(session, order.id)
        if active_attempt is not None:
            raise self.get_conflict("Order already has an active payment attempt.")

        options = await self._collect_options(session, order, actor)
        option = next((item for item in options if item.id == option_id), None)
        if option is None:
            raise self.get_bad_request("Payment option is not available.")

        service = self.payment_registry.get_service(option.payment_system, option.provider_kind)
        if service is None:
            raise self.get_bad_request("Payment provider is not available.")

        attempt_no = await self._get_next_attempt_no(session, order.id)
        now = datetime.now(UTC)
        payment = PaymentORM(
            public_id=uuid4(),
            order_id=order.id,
            attempt_no=attempt_no,
            active_slot=1,
            user_id=actor.id,
            amount=Decimal(order.amount),
            currency=order.currency,
            payment_system=option.payment_system,
            kind=option.provider_kind,
            payment_option_id=option.id,
            state=PaymentState.CREATED.value,
            action_kind=None,
            reason_code=None,
            verification_data=None,
            idempotency_key=key,
            idempotency_fingerprint=fingerprint,
            revision=0,
            expires_at=None,
            paid_at=None,
            cancelled_at=None,
            failed_at=None,
            refunded_at=None,
            created_at=now,
            updated_at=now,
        )
        inserted_payment = await self._insert_attempt(session, payment, actor.id, key, fingerprint)
        if inserted_payment is not payment:
            if inserted_payment.order_id != order.id:
                raise self.get_conflict("Idempotency key is already used for another payment attempt.")
            action = (
                await self._issue_action(session, inserted_payment)
                if inserted_payment.payment_state.accepts_checkout_action
                else None
            )
            return await self.create_payment_serializer().serialize_payment(
                session,
                inserted_payment,
                action=action,
            )

        context = PaymentCreateContext(
            actor=actor,
            order=order,
            payment=payment,
            option=option,
            public_base_url=self.commerce_module.public_base_url,
            idempotency_key=key,
        )
        result = await service.create(session, context)
        if not isinstance(result, PaymentCreateResult):
            raise TypeError("Payment provider must return PaymentCreateResult.")
        self._validate_action(result.action, expected_kind=option.action_kind)
        payment.action_kind = result.action.kind
        payment.expires_at = result.action.expires_at

        if result.action.kind == "completed" and (
                result.verification is None
                or result.verification.state != PaymentState.PAID
        ):
            raise TypeError("A completed checkout action requires a paid verification result.")
        if result.verification is not None and result.verification.state == PaymentState.PAID:
            if result.action.kind != "completed":
                raise TypeError("A synchronously paid attempt requires a completed checkout action.")
        initial_result = result.verification or PaymentVerificationResult(
            state=(
                PaymentState.PROCESSING
                if result.action.kind == "processing"
                else PaymentState.REQUIRES_ACTION
            ),
        )
        await self._apply_result(session, order, payment, initial_result)
        return await self.create_payment_serializer().serialize_payment(
            session,
            payment,
            action=result.action,
        )

    async def get_payment_status(
            self,
            session: AsyncSession,
            payment_public_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> PaymentDTO:
        """Возвращает authoritative REST state после ownership check."""
        payment = await self._get_by_public_id(session, payment_public_id)
        if payment is None:
            raise self.get_not_found("Payment not found.")
        order = await self.get_order(session, payment.order_id)
        if order is None:
            raise self.get_not_found("Payment not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.VIEW)
        return await self.create_payment_serializer().serialize_payment(session, payment)

    async def issue_checkout_action(
            self,
            session: AsyncSession,
            payment_public_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> CheckoutAction:
        """Выпускает новый action через provider без plaintext capability в core ORM."""
        payment = await self._get_by_public_id(session, payment_public_id)
        if payment is None:
            raise self.get_not_found("Payment not found.")
        order = await self.get_order(session, payment.order_id)
        if order is None:
            raise self.get_not_found("Payment not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.CREATE_PAYMENT)
        if not payment.payment_state.accepts_checkout_action:
            raise self.get_conflict("Payment attempt no longer has a checkout action.")
        return await self._issue_action(session, payment)

    async def apply_verification(
            self,
            session: AsyncSession,
            payment_id: int,
            result: PaymentVerificationResult,
    ) -> PaymentDTO:
        """Атомарно применяет уже проверенный provider verdict и product effect."""
        async with session.begin_nested():
            return await self._apply_verification(session, payment_id, result)

    async def _apply_verification(
            self,
            session: AsyncSession,
            payment_id: int,
            result: PaymentVerificationResult,
    ) -> PaymentDTO:
        payment_snapshot = await session.get(PaymentORM, payment_id)
        if payment_snapshot is None:
            raise self.get_not_found("Payment not found.")
        order = await self.get_order_for_update(session, payment_snapshot.order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        payment = await self._get_attempt_for_update(session, payment_id)
        if payment is None or payment.order_id != order.id:
            raise self.get_not_found("Payment not found.")
        await self._apply_result(session, order, payment, result)
        return await self.create_payment_serializer().serialize_payment(session, payment)

    async def cancel_for_order(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> tuple[OrderORM, PaymentORM | None]:
        """Атомарно фиксирует dynamic provider cancellation result."""
        async with session.begin_nested():
            return await self._cancel_for_order(session, order_id, actor)

    async def _cancel_for_order(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> tuple[OrderORM, PaymentORM | None]:
        order = await self.get_order_for_update(session, order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.CANCEL)
        if order.order_state in {OrderState.EXECUTED, OrderState.REFUNDED}:
            raise self.get_conflict("Paid order cannot be cancelled.")
        payment = await self._get_active_attempt_for_update(session, order.id)
        if payment is None:
            return order, None
        if not PaymentStateMachine.can_transition(payment.payment_state, PaymentState.CANCELLED):
            raise self.get_conflict("Payment attempt can no longer be cancelled.")

        service = self.payment_registry.get_service(payment.payment_system, payment.kind)
        if service is None:
            raise self.get_bad_request("Payment provider is not available.")
        cancel_result = await service.cancel(session, payment)
        if not isinstance(cancel_result, PaymentVerificationResult):
            raise TypeError("Payment provider must return PaymentVerificationResult.")
        if cancel_result.state != PaymentState.CANCELLED:
            raise TypeError("Payment provider cancel must return the cancelled state.")
        await self._apply_result(session, order, payment, cancel_result)
        return order, payment

    async def refund_order(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> PaymentDTO:
        """Идемпотентно начинает refund под order/payment locks."""
        order = await self.get_order_for_update(session, order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        await self.check_order_access(session, actor, order, OrderAccessAction.MANAGE)
        payment = await self._get_latest_attempt_for_update(session, order.id)
        if payment is None:
            raise self.get_bad_request("Order payment not found.")
        if payment.payment_state == PaymentState.REFUNDED:
            return await self.create_payment_serializer().serialize_payment(session, payment)
        if payment.payment_state == PaymentState.REFUND_PENDING:
            return await self.create_payment_serializer().serialize_payment(session, payment)
        if payment.payment_state != PaymentState.PAID or order.order_state != OrderState.EXECUTED:
            raise self.get_conflict("Only a paid executed order can be refunded.")

        service = self.payment_registry.get_service(
            payment.payment_system,
            payment.kind,
        )
        if service is None:
            raise self.get_bad_request("Payment provider is not available.")

        async with session.begin_nested():
            await self._apply_result(
                session,
                order,
                payment,
                PaymentVerificationResult(state=PaymentState.REFUND_PENDING),
            )
            refund_result = await service.refund(session, payment)
            if not isinstance(refund_result, PaymentVerificationResult):
                raise TypeError("Payment provider must return PaymentVerificationResult.")
            if refund_result.state not in {
                PaymentState.REFUND_PENDING,
                PaymentState.REFUNDED,
                PaymentState.PAID,
            }:
                raise TypeError("Payment provider returned an invalid refund state.")
            await self._apply_result(session, order, payment, refund_result)
        return await self.create_payment_serializer().serialize_payment(session, payment)

    async def _collect_options(
            self,
            session: AsyncSession,
            order: OrderORM,
            actor: CommerceUserActorDTO,
    ) -> list[PaymentOptionDTO]:
        options: list[PaymentOptionDTO] = []
        used_ids: set[str] = set()
        for payment_system in self.get_available_payment_systems(order.currency):
            service = self.payment_registry.get_service_by_system(payment_system)
            if service is None:
                raise TypeError(f"Payment system '{payment_system}' is not registered.")
            for option in await service.list_options(session, order, actor):
                if not isinstance(option, PaymentOption):
                    raise TypeError("Payment provider options must be PaymentOption values.")
                if option.id in used_ids:
                    raise TypeError(f"Payment option id '{option.id}' is registered more than once.")
                used_ids.add(option.id)
                options.append(
                    PaymentOptionDTO(
                        **option.model_dump(),
                        amount=Decimal(order.amount),
                        currency=order.currency,
                        payment_system=service.payment_system,
                        provider_kind=service.provider_kind,
                    ),
                )
        return options

    async def _issue_action(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> CheckoutAction:
        service = self.payment_registry.get_service(payment.payment_system, payment.kind)
        if service is None:
            raise self.get_bad_request("Payment provider is not available.")
        action = await service.get_action(session, payment)
        self._validate_action(action, expected_kind=payment.action_kind)
        if payment.action_kind is not None and action.kind != payment.action_kind:
            raise TypeError("Payment provider changed checkout action kind for an existing attempt.")
        payment.action_kind = action.kind
        payment.expires_at = action.expires_at
        await session.flush()
        return action

    @staticmethod
    def _validate_action(action: CheckoutAction, *, expected_kind: str | None) -> None:
        if not isinstance(action, CheckoutAction):
            raise TypeError("Payment provider must return CheckoutAction.")
        if expected_kind is not None and action.kind != expected_kind:
            raise TypeError("Payment provider returned an unexpected checkout action kind.")
        if action.expires_at is not None and action.expires_at <= datetime.now(UTC):
            raise TypeError("Payment provider returned an expired checkout action.")

    async def _apply_result(
            self,
            session: AsyncSession,
            order: OrderORM,
            payment: PaymentORM,
            result: PaymentVerificationResult,
    ) -> bool:
        if not isinstance(result, PaymentVerificationResult):
            raise TypeError("Payment provider must return PaymentVerificationResult.")
        current_state = payment.payment_state
        if not PaymentStateMachine.can_transition(current_state, result.state):
            raise self.get_conflict(
                f"Payment cannot transition from {current_state.value} to {result.state.value}.",
            )

        await self._record_evidence(session, payment, result)
        evidence_payload = dict(result.evidence) or None
        if (
            current_state == result.state
            and payment.reason_code == result.reason_code
            and payment.verification_data == evidence_payload
        ):
            return False

        now = datetime.now(UTC)
        payment.state = result.state.value
        payment.active_slot = 1 if result.state.occupies_active_slot else None
        payment.reason_code = result.reason_code
        payment.verification_data = evidence_payload
        payment.revision += 1
        payment.updated_at = now

        if result.state == PaymentState.PAID:
            if order.order_state in {OrderState.CANCELLED, OrderState.REFUNDED}:
                raise self.get_conflict("Cancelled or refunded order cannot be finalized.")
            payment.paid_at = payment.paid_at or now
            await self.create_order_runtime().execute_order(session, order, payment)
        elif result.state == PaymentState.CANCELLED:
            payment.cancelled_at = payment.cancelled_at or now
        elif result.state == PaymentState.FAILED:
            payment.failed_at = payment.failed_at or now
        elif result.state == PaymentState.REFUNDED:
            payment.refunded_at = payment.refunded_at or now
            await self.create_order_runtime().revoke_order(session, order, payment)

        self._record_outbox(session, order, payment, now)
        await session.flush()
        return True

    async def _record_evidence(
            self,
            session: AsyncSession,
            payment: PaymentORM,
            result: PaymentVerificationResult,
    ) -> None:
        if result.evidence_key is None:
            return
        query = (
            select(PaymentEvidenceORM)
            .where(
                PaymentEvidenceORM.payment_system == payment.payment_system,
                PaymentEvidenceORM.evidence_key == result.evidence_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        evidence = (await session.execute(query)).scalar_one_or_none()
        now = datetime.now(UTC)
        if evidence is None:
            try:
                async with session.begin_nested():
                    evidence = PaymentEvidenceORM(
                        payment_id=payment.id,
                        payment_system=payment.payment_system,
                        evidence_key=result.evidence_key,
                        state=result.state.value,
                        reason_code=result.reason_code,
                        payload=dict(result.evidence),
                        first_seen_at=now,
                        updated_at=now,
                    )
                    session.add(evidence)
                    await session.flush()
            except IntegrityError:
                evidence = (await session.execute(query)).scalar_one_or_none()
        if evidence is None:
            raise self.get_conflict("Payment evidence could not be claimed.")
        if evidence.payment_id != payment.id:
            raise self.get_conflict("Payment evidence is already linked to another attempt.")
        evidence.state = result.state.value
        evidence.reason_code = result.reason_code
        evidence.payload = dict(result.evidence)
        evidence.updated_at = now

    def _record_outbox(
            self,
            session: AsyncSession,
            order: OrderORM,
            payment: PaymentORM,
            occurred_at: datetime,
    ) -> None:
        session.add(
            PaymentOutboxEventORM(
                event_id=uuid4(),
                event_type=self.event_type,
                payment_id=payment.id,
                payment_public_id=payment.public_id,
                order_id=payment.order_id,
                user_id=order.user_id if order.user_id is not None else payment.user_id,
                revision=payment.revision,
                payload={
                    "order_public_id": str(payment.order_id),
                    "payment_public_id": str(payment.public_id),
                    "revision": payment.revision,
                    "state": payment.state,
                },
                occurred_at=occurred_at,
                available_at=occurred_at,
                claimed_at=None,
                claimed_by=None,
                delivered_at=None,
                delivery_attempts=0,
                last_error=None,
            ),
        )

    async def _insert_attempt(
            self,
            session: AsyncSession,
            payment: PaymentORM,
            actor_id: int,
            key: str,
            fingerprint: str,
    ) -> PaymentORM:
        try:
            async with session.begin_nested():
                session.add(payment)
                await session.flush()
            return payment
        except IntegrityError:
            existing = await self._get_idempotent_attempt(session, actor_id, key)
            if existing is not None:
                self._check_idempotency_fingerprint(existing.idempotency_fingerprint, fingerprint)
                return existing
            active = await self._get_active_attempt(session, payment.order_id)
            if active is not None:
                raise self.get_conflict("Order already has an active payment attempt.")
            raise

    @staticmethod
    async def _get_attempt_for_update(session: AsyncSession, payment_id: int) -> PaymentORM | None:
        query = (
            select(PaymentORM)
            .where(PaymentORM.id == payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_active_attempt(session: AsyncSession, order_id: UUID) -> PaymentORM | None:
        query = select(PaymentORM).where(
            PaymentORM.order_id == order_id,
            PaymentORM.active_slot == 1,
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_active_attempt_for_update(session: AsyncSession, order_id: UUID) -> PaymentORM | None:
        query = (
            select(PaymentORM)
            .where(PaymentORM.order_id == order_id, PaymentORM.active_slot == 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_latest_attempt(session: AsyncSession, order_id: UUID) -> PaymentORM | None:
        query = (
            select(PaymentORM)
            .where(PaymentORM.order_id == order_id)
            .order_by(PaymentORM.attempt_no.desc())
            .limit(1)
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_latest_attempt_for_update(session: AsyncSession, order_id: UUID) -> PaymentORM | None:
        query = (
            select(PaymentORM)
            .where(PaymentORM.order_id == order_id)
            .order_by(PaymentORM.attempt_no.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_idempotent_attempt(
            session: AsyncSession,
            user_id: int,
            key: str,
    ) -> PaymentORM | None:
        query = select(PaymentORM).where(
            PaymentORM.user_id == user_id,
            PaymentORM.idempotency_key == key,
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_next_attempt_no(session: AsyncSession, order_id: UUID) -> int:
        query = select(func.coalesce(func.max(PaymentORM.attempt_no), 0)).where(PaymentORM.order_id == order_id)
        return int((await session.execute(query)).scalar_one()) + 1

    @staticmethod
    async def _get_by_public_id(
            session: AsyncSession,
            payment_public_id: str | UUID,
    ) -> PaymentORM | None:
        try:
            normalized_id = (
                payment_public_id
                if isinstance(payment_public_id, UUID)
                else UUID(str(payment_public_id))
            )
        except (TypeError, ValueError):
            return None
        query = select(PaymentORM).where(PaymentORM.public_id == normalized_id)
        return (await session.execute(query)).scalar_one_or_none()

    def _normalize_idempotency_key(self, value: str) -> str:
        try:
            return Idempotency.normalize_key(value)
        except ValueError as exc:
            raise self.get_bad_request(str(exc)) from exc

    def _check_idempotency_fingerprint(self, current: str, incoming: str) -> None:
        if current != incoming:
            raise self.get_conflict("Idempotency key was already used with a different payload.")
