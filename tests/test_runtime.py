from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from commercexl import (
    AbstractPaymentService,
    BalancePaymentService,
    BaseConfig,
    CommerceBase,
    CommerceModule,
    CommerceUserActorDTO,
    CheckoutAction,
    DefaultOrderItemService,
    HandMadePaymentService,
    OrderItemState,
    OrderState,
    PaymentConfigBuilder,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentProviderRegistration,
    PaymentState,
    PaymentVerificationResult,
    ProductORM,
    ProductOrderConfig,
    ProductOrderConfigBuilder,
    ProductPriceORM,
    UserCreditsBalanceORM,
)
from commercexl.models import OrderItemORM, PaymentEvidenceORM, PaymentORM, PaymentOutboxEventORM
from commercexl.services.products.base import AbstractProductService, DefaultProductService


class DemoProductORM(CommerceBase):
    __tablename__ = "demo_product"

    product_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), primary_key=True)


class DemoItemORM(CommerceBase):
    __tablename__ = "demo_order_item"

    order_item_id: Mapped[int] = mapped_column(ForeignKey("commerce_orderitem.id"), primary_key=True)
    note: Mapped[str] = mapped_column(String(255), nullable=False)
    give_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("1")}


class DemoBalanceConfig(DemoConfig):
    PAYMENT_SYSTEMS = {"USD": ("balance",)}


class FailingPaymentConfig(DemoConfig):
    PAYMENT_SYSTEMS = {"USD": ("failing",)}


class FailingPaymentService(AbstractPaymentService):
    async def list_options(self, session, order, actor) -> tuple[PaymentOption, ...]:
        _ = session
        _ = order
        _ = actor
        return (PaymentOption(id="failing", label="Failing", action_kind="manual"),)

    async def create(self, session, context: PaymentCreateContext) -> PaymentCreateResult:
        context.payment.reason_code = "must_rollback"
        await session.flush()
        raise RuntimeError("provider failed")

    async def get_action(self, session, payment) -> CheckoutAction:
        _ = session
        _ = payment
        return CheckoutAction(kind="manual", payload={"message": "Failing provider"})

    async def cancel(self, session, payment) -> PaymentVerificationResult:
        _ = session
        _ = payment
        return PaymentVerificationResult(state=PaymentState.CANCELLED)


class DemoOrderItemService(DefaultOrderItemService):
    async def create_item_record(self, payload: dict[str, object], amount: Decimal) -> DemoItemORM:
        _ = amount
        self.item_record = DemoItemORM(
            order_item_id=self.order_item.id,
            note=str(payload["note"]),
            give_count=0,
            is_revoked=False,
        )
        return self.item_record


class DemoProductService(AbstractProductService[DemoItemORM]):
    kind = "demo"
    product_kinds = ("demo",)
    item_kinds = ("demoitem",)
    product_model = DemoProductORM
    item_model = DemoItemORM

    async def post_give(
            self,
            session,
            order,
            order_item,
            item_record: DemoItemORM | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        if item_record is not None:
            item_record.give_count += 1
            item_record.changed_at = now

    async def revoke_give(
            self,
            session,
            order,
            order_item,
            item_record: DemoItemORM | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        if item_record is not None:
            item_record.is_revoked = True
            item_record.changed_at = now


def create_demo_commerce(*, balance: bool = False) -> CommerceModule:
    service = BalancePaymentService if balance else HandMadePaymentService
    registration = PaymentProviderRegistration(
        "balance" if balance else "handmade",
        "balance" if balance else "handmade",
        service,
    )
    return CommerceModule(
        config_class=DemoBalanceConfig if balance else DemoConfig,
        product_orders=ProductOrderConfigBuilder(
            ProductOrderConfig(DemoProductService, DemoOrderItemService),
        ),
        payments=PaymentConfigBuilder(registration),
        public_base_url="https://commerce.example.com",
    )


async def add_demo_product(db_session, product_id: int = 1, amount: str = "15.125") -> None:
    now = datetime.now(UTC)
    db_session.add(
        ProductORM(
            id=product_id,
            name="Demo",
            pic=None,
            description="Demo",
            short_description="Demo",
            is_available=True,
            is_installment_available=False,
            kind="demo",
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(DemoProductORM(product_ptr_id=product_id))
    db_session.add(
        ProductPriceORM(
            product_id=product_id,
            currency="USD",
            amount=Decimal(amount),
            exponent=None,
            offset=None,
        ),
    )
    await db_session.commit()


def order_payload(product_id: int = 1, note: str = "first") -> dict[str, object]:
    return {"product": product_id, "note": note, "currency": "USD"}


@pytest.mark.asyncio
async def test_create_order_is_two_phase_and_idempotent(db_session):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    runtime = commerce.create_order_runtime()
    actor = CommerceUserActorDTO(id=7)

    first = await runtime.create_order(db_session, actor, order_payload(), "order-key")
    second = await runtime.create_order(db_session, actor, order_payload(), "order-key")

    assert first.id == second.id
    assert first.amount == Decimal("15.125")
    assert first.model_dump(mode="json")["amount"] == "15.125"
    order = await runtime.get_order(db_session, first.id)
    assert order is not None
    assert order.order_state == OrderState.READY_FOR_PAYMENT
    assert await db_session.scalar(select(func.count()).select_from(PaymentORM)) == 0

    with pytest.raises(HTTPException) as exc_info:
        await runtime.create_order(db_session, actor, order_payload(note="changed"), "order-key")
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_handmade_attempt_is_explicitly_unpaid_and_owner_scoped(db_session):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    order = await commerce.create_order_runtime().create_order(
        db_session,
        CommerceUserActorDTO(id=7),
        order_payload(),
        "order-key",
    )

    runtime = commerce.create_payment_runtime()
    options = await runtime.list_payment_options(db_session, order.id, CommerceUserActorDTO(id=7))
    payment = await runtime.create_attempt(
        db_session,
        order.id,
        options.options[0].id,
        CommerceUserActorDTO(id=7),
        "payment-key",
    )

    assert payment.state == PaymentState.REQUIRES_ACTION
    assert payment.action is not None
    assert payment.action.kind == "manual"
    assert payment.model_dump(mode="json")["amount"] == "15.125"
    stored_order = await commerce.create_order_runtime().get_order(db_session, order.id)
    assert stored_order is not None
    assert stored_order.order_state == OrderState.READY_FOR_PAYMENT
    assert await db_session.scalar(select(func.count()).select_from(PaymentOutboxEventORM)) == 1
    assert (
        await runtime.list_payment_options(db_session, order.id, CommerceUserActorDTO(id=7))
    ).options == []

    with pytest.raises(HTTPException) as exc_info:
        await runtime.create_attempt(
            db_session,
            order.id,
            "handmade",
            CommerceUserActorDTO(id=8),
            "foreign-payment-key",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_verification_finalizes_once_and_claims_evidence(db_session):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    actor = CommerceUserActorDTO(id=7)
    order_result = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    payment_dto = await commerce.create_payment_runtime().create_attempt(
        db_session,
        order_result.id,
        "handmade",
        actor,
        "payment-key",
    )
    payment = await db_session.scalar(select(PaymentORM).where(PaymentORM.public_id == payment_dto.id))
    assert payment is not None

    result = PaymentVerificationResult(
        state=PaymentState.PAID,
        evidence_key="manual:receipt-1",
        evidence={"receipt": "receipt-1"},
    )
    await commerce.create_payment_runtime().apply_verification(db_session, payment.id, result)
    await commerce.create_payment_runtime().apply_verification(db_session, payment.id, result)

    order = await commerce.create_order_runtime().get_order(db_session, order_result.id)
    assert order is not None
    assert order.order_state == OrderState.EXECUTED
    item = (await commerce.create_base_runtime().get_order_items(db_session, order.id))[0]
    assert item.item_state == OrderItemState.EXECUTED
    item_record = await db_session.get(DemoItemORM, item.id)
    assert item_record is not None
    assert item_record.give_count == 1
    assert payment.payment_state == PaymentState.PAID
    assert payment.active_slot == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvidenceORM)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentOutboxEventORM)) == 2
    events = list(
        (
            await db_session.execute(
                select(PaymentOutboxEventORM).order_by(PaymentOutboxEventORM.revision),
            )
        ).scalars(),
    )
    assert events[-1].payload == {
        "order_public_id": str(order_result.id),
        "payment_public_id": str(payment.public_id),
        "revision": 2,
        "state": "paid",
    }


@pytest.mark.asyncio
async def test_terminal_failed_attempt_allows_next_attempt(db_session):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    actor = CommerceUserActorDTO(id=7)
    order = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    runtime = commerce.create_payment_runtime()
    first = await runtime.create_attempt(db_session, order.id, "handmade", actor, "payment-1")
    first_record = await db_session.scalar(select(PaymentORM).where(PaymentORM.public_id == first.id))
    assert first_record is not None
    await runtime.apply_verification(
        db_session,
        first_record.id,
        PaymentVerificationResult(state=PaymentState.FAILED, reason_code="provider_failed"),
    )

    second = await runtime.create_attempt(db_session, order.id, "handmade", actor, "payment-2")
    assert second.attempt_no == 2
    assert second.state == PaymentState.REQUIRES_ACTION


@pytest.mark.asyncio
async def test_provider_failure_rolls_back_canonical_attempt_and_outbox(db_session):
    await add_demo_product(db_session)
    commerce = CommerceModule(
        config_class=FailingPaymentConfig,
        product_orders=ProductOrderConfigBuilder(
            ProductOrderConfig(DemoProductService, DemoOrderItemService),
        ),
        payments=PaymentConfigBuilder(
            PaymentProviderRegistration("failing", "failing", FailingPaymentService),
        ),
    )
    actor = CommerceUserActorDTO(id=7)
    order = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        await commerce.create_payment_runtime().create_attempt(
            db_session,
            order.id,
            "failing",
            actor,
            "payment-key",
        )
    await db_session.commit()

    assert await db_session.scalar(select(func.count()).select_from(PaymentORM)) == 0
    assert await db_session.scalar(select(func.count()).select_from(PaymentOutboxEventORM)) == 0


@pytest.mark.asyncio
async def test_finalization_failure_rolls_back_payment_order_evidence_and_outbox(db_session, monkeypatch):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    actor = CommerceUserActorDTO(id=7)
    order_result = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    payment_dto = await commerce.create_payment_runtime().create_attempt(
        db_session,
        order_result.id,
        "handmade",
        actor,
        "payment-key",
    )
    payment = await db_session.scalar(select(PaymentORM).where(PaymentORM.public_id == payment_dto.id))
    assert payment is not None

    async def fail_product_effect(*args, **kwargs):
        _ = args
        _ = kwargs
        raise RuntimeError("product effect failed")

    monkeypatch.setattr(DemoProductService, "post_give", fail_product_effect)
    with pytest.raises(RuntimeError, match="product effect failed"):
        await commerce.create_payment_runtime().apply_verification(
            db_session,
            payment.id,
            PaymentVerificationResult(
                state=PaymentState.PAID,
                evidence_key="manual:rollback",
            ),
        )
    await db_session.commit()
    await db_session.refresh(payment)

    order = await commerce.create_order_runtime().get_order(db_session, order_result.id)
    assert order is not None and order.order_state == OrderState.READY_FOR_PAYMENT
    assert payment.payment_state == PaymentState.REQUIRES_ACTION
    assert payment.revision == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvidenceORM)) == 0
    assert await db_session.scalar(select(func.count()).select_from(PaymentOutboxEventORM)) == 1


@pytest.mark.asyncio
async def test_cancel_uses_provider_contract_before_order_transition(db_session):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    actor = CommerceUserActorDTO(id=7)
    order = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    await commerce.create_payment_runtime().create_attempt(
        db_session,
        order.id,
        "handmade",
        actor,
        "payment-key",
    )

    cancelled = await commerce.create_order_runtime().cancel_order(db_session, order.id, actor)
    assert cancelled.state == OrderState.CANCELLED
    assert cancelled.payment is not None
    assert cancelled.payment.state == PaymentState.CANCELLED
    stored_items = await commerce.create_base_runtime().get_order_items(db_session, order.id)
    assert stored_items[0].item_state == OrderItemState.CANCELLED


@pytest.mark.asyncio
async def test_paid_order_rejects_cancel_before_provider_side_effect(db_session, monkeypatch):
    await add_demo_product(db_session)
    commerce = create_demo_commerce()
    actor = CommerceUserActorDTO(id=7)
    order = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    payment_dto = await commerce.create_payment_runtime().create_attempt(
        db_session,
        order.id,
        "handmade",
        actor,
        "payment-key",
    )
    payment = await db_session.scalar(select(PaymentORM).where(PaymentORM.public_id == payment_dto.id))
    assert payment is not None
    await commerce.create_payment_runtime().apply_verification(
        db_session,
        payment.id,
        PaymentVerificationResult(
            state=PaymentState.PAID,
            evidence_key="manual:paid-before-cancel",
        ),
    )

    provider_calls: list[int] = []

    async def record_cancel(self, session, payment_record):
        _ = self
        _ = session
        provider_calls.append(payment_record.id)
        return PaymentVerificationResult(state=PaymentState.CANCELLED)

    monkeypatch.setattr(HandMadePaymentService, "cancel", record_cancel)
    with pytest.raises(HTTPException) as exc_info:
        await commerce.create_order_runtime().cancel_order(db_session, order.id, actor)

    assert exc_info.value.status_code == 409
    assert provider_calls == []


@pytest.mark.asyncio
async def test_balance_payment_and_refund_use_common_lifecycle(db_session):
    await add_demo_product(db_session, amount="15")
    now = datetime.now(UTC)
    db_session.add(
        UserCreditsBalanceORM(
            user_id=7,
            amount=Decimal("100"),
            created_at=now,
            updated_at=now,
        ),
    )
    await db_session.commit()

    commerce = create_demo_commerce(balance=True)
    actor = CommerceUserActorDTO(id=7)
    order = await commerce.create_order_runtime().create_order(
        db_session,
        actor,
        order_payload(),
        "order-key",
    )
    runtime = commerce.create_payment_runtime()
    payment = await runtime.create_attempt(db_session, order.id, "balance", actor, "payment-key")
    repeated = await runtime.create_attempt(db_session, order.id, "balance", actor, "payment-key")

    assert payment.id == repeated.id
    assert payment.state == PaymentState.PAID
    assert payment.action is not None and payment.action.kind == "completed"
    balance = await db_session.scalar(
        select(UserCreditsBalanceORM).where(UserCreditsBalanceORM.user_id == actor.id),
    )
    assert balance is not None
    assert balance.amount == Decimal("85")

    manager = CommerceUserActorDTO(id=99, permissions=frozenset({"commerce.manage"}))
    refunded = await runtime.refund_order(db_session, order.id, manager)
    repeated_refund = await runtime.refund_order(db_session, order.id, manager)
    assert refunded.state == PaymentState.REFUNDED
    assert repeated_refund.state == PaymentState.REFUNDED
    stored_order = await commerce.create_order_runtime().get_order(db_session, order.id)
    assert stored_order is not None and stored_order.order_state == OrderState.REFUNDED
    assert balance.amount == Decimal("100")
    assert await db_session.scalar(select(func.count()).select_from(PaymentOutboxEventORM)) == 3


@pytest.mark.asyncio
async def test_default_order_item_service_allows_product_without_child_record():
    class NoChildProductService(DefaultProductService[None]):
        kind = "no_child"
        product_kinds = ("nochild",)
        item_kinds = ("nochilditem",)
        item_model = None
        default_order_item_service_class = DefaultOrderItemService

    commerce = create_demo_commerce()
    product_service = NoChildProductService(commerce.create_base_runtime())
    order = type("Order", (), {"currency": "USD"})()
    order_item = type("OrderItem", (), {"product_id": 1, "kind": "nochilditem", "id": 1})()
    order_service = product_service.create_order_item_service(order, order_item).bind(None)

    item_record = await order_service.create_item_record({}, Decimal("10"))
    assert item_record is None
