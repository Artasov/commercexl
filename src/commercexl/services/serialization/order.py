from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO, OrderItemDTO
from commercexl.models import OrderItemORM, OrderORM, PaymentORM, ProductORM
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.promocode.base import Promocode
from commercexl.services.serialization.product import ProductSerializer


class OrderSerializer(BaseRuntime):
    """Сериализует заказ как список items и последнюю payment attempt."""

    async def get_user_orders(self, session: AsyncSession, user_id: int) -> list[OrderDTO]:
        query = select(OrderORM).where(OrderORM.user_id == user_id).order_by(OrderORM.created_at.desc())
        orders = list((await session.execute(query)).scalars())
        return [await self.serialize_order(session, order) for order in orders]

    async def get_order_item_payload(self, session: AsyncSession, order_item: OrderItemORM) -> dict:
        _handler, item_record, item_service = await super().get_order_item_payload(session, order_item)
        product_payload = None
        requested_amount = None
        credited_amount = None
        key = None
        license_hours = None

        if item_record is not None:
            if hasattr(item_record, "requested_amount"):
                requested_amount = Decimal(item_record.requested_amount)
                credited_amount = (
                    Decimal(item_record.credited_amount)
                    if item_record.credited_amount is not None
                    else None
                )
            if hasattr(item_record, "key"):
                key = str(item_record.key)
            if hasattr(item_record, "license_hours"):
                license_hours = item_record.license_hours

        product_id = item_service.get_product_id() if item_service is not None else order_item.product_id
        product: ProductORM | None = await session.get(ProductORM, product_id)
        if product is not None:
            product_payload = await ProductSerializer(commerce_module=self.commerce_module).serialize_product(
                session,
                product,
            )
        return {
            "product": product_payload,
            "requested_amount": requested_amount,
            "credited_amount": credited_amount,
            "key": key,
            "license_hours": license_hours,
        }

    async def serialize_order_item(self, session: AsyncSession, order_item: OrderItemORM) -> OrderItemDTO:
        payload = await self.get_order_item_payload(session, order_item)
        return OrderItemDTO(
            id=order_item.id,
            amount=order_item.amount,
            state=order_item.item_state,
            product=payload["product"],
            requested_amount=payload["requested_amount"],
            credited_amount=payload["credited_amount"],
            key=payload["key"],
            license_hours=payload["license_hours"],
        )

    async def serialize_order(self, session: AsyncSession, order: OrderORM) -> OrderDTO:
        items = await self.get_order_items(session, order.id)
        latest_payment = await self.get_latest_payment(session, order.id)
        payment = (
            await self.create_payment_serializer().serialize_payment(session, latest_payment)
            if latest_payment is not None
            else None
        )
        return OrderDTO(
            id=order.id,
            amount=order.amount,
            currency=order.currency,
            state=order.order_state,
            payment=payment,
            promocode=await Promocode(commerce_module=self.commerce_module).serialize_promocode(
                session,
                order.promocode_id,
            ),
            created_at=self.as_utc(order.created_at),
            updated_at=self.as_utc(order.updated_at),
            items=[await self.serialize_order_item(session, item) for item in items],
        )

    @staticmethod
    async def get_latest_payment(session: AsyncSession, order_id) -> PaymentORM | None:
        query = (
            select(PaymentORM)
            .where(PaymentORM.order_id == order_id)
            .order_by(PaymentORM.attempt_no.desc())
            .limit(1)
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        """Нормализует persisted datetime в aware UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
