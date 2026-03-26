from __future__ import annotations
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl import (
    BaseConfig,
    CommerceBase,
    CommerceModule,
    CommerceUserActorDTO,
    DefaultOrderItemService,
    HandMadePaymentService,
    OrderItemORM,
    OrderORM,
    PaymentConfigBuilder,
    ProductORM,
    ProductOrderConfig,
    ProductOrderConfigBuilder,
    ProductPriceORM,
)
from commercexl.models import PaymentORM
from commercexl.services.products.base import AbstractProductService, DefaultProductService


class DemoProductORM(CommerceBase):
    __tablename__ = "demo_product"

    product_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), primary_key=True)


class DemoItemORM(CommerceBase):
    __tablename__ = "demo_order_item"

    order_item_id: Mapped[int] = mapped_column(ForeignKey("commerce_orderitem.id"), primary_key=True)
    note: Mapped[str] = mapped_column(String(255), nullable=False)
    is_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("100")}


class DemoOrderItemService(DefaultOrderItemService):
    async def create_item_record(self, payload: dict[str, object], amount: Decimal) -> DemoItemORM:
        _ = amount
        self.item_record = DemoItemORM(order_item_id=self.order_item.id, note=str(payload["note"]))
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
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: DemoItemORM | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        if item_record is not None:
            item_record.is_given = True
            item_record.changed_at = now

    async def revoke_give(
            self,
            session,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: DemoItemORM | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        if item_record is not None:
            item_record.is_revoked = True
            item_record.changed_at = now


def create_demo_commerce() -> CommerceModule:
    return CommerceModule(
        config_class=DemoConfig,
        product_orders=ProductOrderConfigBuilder(
            ProductOrderConfig(DemoProductService, DemoOrderItemService),
        ),
        payments=PaymentConfigBuilder(HandMadePaymentService),
    )


@pytest.mark.asyncio
async def test_create_order_builds_checkout_order_and_item(db_session):
    now = datetime.now(UTC)
    db_session.add(
        ProductORM(
            id=1,
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
    db_session.add(DemoProductORM(product_ptr_id=1))
    db_session.add(
        ProductPriceORM(
            product_id=1,
            currency="USD",
            amount=Decimal("15"),
            exponent=None,
            offset=None,
        ),
    )
    await db_session.commit()

    commerce = create_demo_commerce()
    runtime = commerce.create_order_runtime()

    result = await runtime.create_order(
        db_session,
        CommerceUserActorDTO(id=7),
        {
            "product": 1,
            "note": "first",
            "currency": "USD",
            "payment_system": "handmade",
        },
        "https://example.com",
    )
    await db_session.commit()

    order = await runtime.get_order(db_session, result.id)
    assert order is not None
    assert order.is_inited is True
    assert order.amount == Decimal("15")

    items = await commerce.create_base_runtime().get_order_items(db_session, order.id)
    assert len(items) == 1
    assert items[0].kind == "demoitem"

    _handler, item_record, _service = await commerce.create_base_runtime().get_order_item_payload(db_session, items[0])
    assert item_record is not None
    assert item_record.note == "first"

    payment = await db_session.get(PaymentORM, order.payment_id)
    assert payment is not None
    assert payment.kind == "handmadepayment"


@pytest.mark.asyncio
async def test_execute_and_refund_order_use_post_and_revoke_hooks(db_session):
    now = datetime.now(UTC)
    order_id = uuid4()
    db_session.add(
        ProductORM(
            id=2,
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
    db_session.add(DemoProductORM(product_ptr_id=2))
    db_session.add(
        OrderORM(
            id=order_id,
            user_id=3,
            amount=Decimal("10"),
            currency="USD",
            payment_system="handmade",
            payment_id=1,
            promocode_id=None,
            is_inited=True,
            is_executed=False,
            is_paid=True,
            is_cancelled=False,
            is_refunded=False,
            kind="order",
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        OrderItemORM(
            id=1,
            order_id=order_id,
            product_id=2,
            amount=Decimal("10"),
            kind="demoitem",
            is_inited=True,
            is_executed=False,
            is_paid=True,
            is_cancelled=False,
            is_refunded=False,
            created_at=now,
            updated_at=now,
        ),
    )
    db_session.add(
        DemoItemORM(
            order_item_id=1,
            note="demo",
            is_given=False,
            is_revoked=False,
            changed_at=None,
        ),
    )
    db_session.add(
        PaymentORM(
            id=1,
            user_id=3,
            amount=Decimal("10"),
            currency="USD",
            payment_url=None,
            is_paid=True,
            kind="handmadepayment",
            created_at=now,
            updated_at=now,
        ),
    )
    await db_session.commit()

    commerce = create_demo_commerce()
    runtime = commerce.create_order_runtime()
    order = await runtime.get_order(db_session, order_id)
    assert order is not None

    await runtime.execute_order(db_session, order)
    await db_session.commit()

    item_record = await db_session.get(DemoItemORM, 1)
    assert item_record is not None
    assert item_record.is_given is True

    await runtime.refund_order(db_session, order)
    await db_session.commit()

    refreshed_order = await runtime.get_order(db_session, order_id)
    assert refreshed_order is not None
    assert refreshed_order.is_refunded is True

    refreshed_item = await db_session.get(OrderItemORM, 1)
    assert refreshed_item is not None
    assert refreshed_item.is_refunded is True

    item_record = await db_session.get(DemoItemORM, 1)
    assert item_record is not None
    assert item_record.is_revoked is True


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
    order = OrderORM(currency="USD")
    order.id = uuid4()
    order_item = OrderItemORM(product_id=1, kind="nochilditem")

    order_service = product_service.create_order_item_service(order, order_item).bind(None)

    item_record = await order_service.create_item_record({}, Decimal("10"))
    assert item_record is None
