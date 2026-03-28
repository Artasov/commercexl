from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO, OrderItemDTO
from commercexl.models import OrderItemORM, OrderORM, ProductORM
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.promocode.base import Promocode
from commercexl.services.serialization.product import ProductSerializer


class OrderSerializer(BaseRuntime):
    """Сериализация заказа и его позиций."""

    @staticmethod
    def create_product_serializer() -> ProductSerializer:
        return ProductSerializer()

    @staticmethod
    def create_promocode_service() -> Promocode:
        return Promocode()

    async def get_user_orders(self, session: AsyncSession, user_id: int) -> list[OrderDTO]:
        query = select(OrderORM).where(OrderORM.user_id == user_id).order_by(OrderORM.created_at.desc())
        orders = list((await session.execute(query)).scalars())
        return [await self.serialize_order(session, order) for order in orders]

    async def get_order_item_payload(self, session: AsyncSession, order_item: OrderItemORM) -> dict:
        handler, item_record, item_service = await super().get_order_item_payload(session, order_item)
        product_serializer = self.create_product_serializer()

        product_payload = None
        requested_amount = None
        credited_amount = None
        key = None
        license_hours = None

        if item_record is not None:
            if hasattr(item_record, "requested_amount"):
                requested_amount = float(item_record.requested_amount)
                credited_amount = float(item_record.credited_amount) if item_record.credited_amount is not None else None
            if hasattr(item_record, "key"):
                key = str(item_record.key)
            if hasattr(item_record, "license_hours"):
                license_hours = item_record.license_hours

        product_id = item_service.get_product_id() if item_service is not None else order_item.product_id
        product: ProductORM | None = await session.get(ProductORM, product_id)
        if product is not None:
            product_payload = await product_serializer.serialize_product(session, product)

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
            id=str(order_item.id),
            amount=float(order_item.amount) if order_item.amount is not None else None,
            currency=(await session.get(OrderORM, order_item.order_id)).currency,
            state=order_item.state,
            is_inited=order_item.is_inited,
            is_paid=order_item.is_paid,
            is_executed=order_item.is_executed,
            is_cancelled=order_item.is_cancelled,
            is_refunded=order_item.is_refunded,
            product=payload["product"],
            requested_amount=payload["requested_amount"],
            credited_amount=payload["credited_amount"],
            key=payload["key"],
            license_hours=payload["license_hours"],
        )

    async def serialize_order(self, session: AsyncSession, order: OrderORM) -> OrderDTO:
        payment_serializer = self.create_payment_serializer()
        promocode_service = self.create_promocode_service()
        payment = await payment_serializer.serialize_payment(session, order.payment_id) if order.payment_id else None
        items = await self.get_order_items(session, order.id)
        if len(items) > 1:
            return OrderDTO(
                id=str(order.id),
                amount=float(order.amount) if order.amount is not None else None,
                payment=payment,
                currency=order.currency,
                payment_system=order.payment_system,
                promocode=await promocode_service.serialize_promocode(session, order.promocode_id),
                created_at=order.created_at.isoformat(),
                updated_at=order.updated_at.isoformat(),
                state=order.state,
                is_inited=order.is_inited,
                is_paid=order.is_paid,
                is_executed=order.is_executed,
                is_cancelled=order.is_cancelled,
                is_refunded=order.is_refunded,
                items=[await self.serialize_order_item(session, order_item) for order_item in items],
            )

        payload = await self.get_order_item_payload(session, items[0]) if items else {
            "product": None,
            "requested_amount": None,
            "credited_amount": None,
            "key": None,
            "license_hours": None,
        }
        return OrderDTO(
            id=str(order.id),
            amount=float(order.amount) if order.amount is not None else None,
            payment=payment,
            currency=order.currency,
            payment_system=order.payment_system,
            promocode=await promocode_service.serialize_promocode(session, order.promocode_id),
            created_at=order.created_at.isoformat(),
            updated_at=order.updated_at.isoformat(),
            state=order.state,
            is_inited=order.is_inited,
            is_paid=order.is_paid,
            is_executed=order.is_executed,
            is_cancelled=order.is_cancelled,
            is_refunded=order.is_refunded,
            product=payload["product"],
            requested_amount=payload["requested_amount"],
            credited_amount=payload["credited_amount"],
            key=payload["key"],
            license_hours=payload["license_hours"],
        )


