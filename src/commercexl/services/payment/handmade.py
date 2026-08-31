from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO
from commercexl.models import HandMadePaymentORM, OrderORM, PaymentORM
from commercexl.payment import (
    CheckoutAction,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentState,
    PaymentVerificationResult,
)
from commercexl.services.payment.base import AbstractPaymentService


class HandMadePaymentService(AbstractPaymentService):
    """Ручная неоплаченная попытка с явным manual action."""

    action_payload = {"message": "Awaiting manual payment confirmation."}

    async def list_options(
            self,
            session: AsyncSession,
            order: OrderORM,
            actor: CommerceUserActorDTO,
    ) -> tuple[PaymentOption, ...]:
        _ = session
        _ = order
        _ = actor
        return (
            PaymentOption(
                id="handmade",
                label="Manual payment",
                action_kind="manual",
            ),
        )

    async def create(
            self,
            session: AsyncSession,
            context: PaymentCreateContext,
    ) -> PaymentCreateResult:
        session.add(HandMadePaymentORM(payment_ptr_id=context.payment.id))
        await session.flush()
        return PaymentCreateResult(
            action=CheckoutAction(kind="manual", payload=self.action_payload),
        )

    async def get_action(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> CheckoutAction:
        _ = session
        _ = payment
        return CheckoutAction(kind="manual", payload=self.action_payload)

    async def cancel(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> PaymentVerificationResult:
        _ = session
        _ = payment
        return PaymentVerificationResult(state=PaymentState.CANCELLED)
