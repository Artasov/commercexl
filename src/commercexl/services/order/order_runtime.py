from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO
from commercexl.models import OrderItemORM, OrderORM, PaymentORM, PromocodeUsageORM
from commercexl.services.order.order_create import OrderCreate
from commercexl.services.promocode.base import Promocode


class OrderRuntime(OrderCreate):
    """Р–РёР·РЅРµРЅРЅС‹Р№ С†РёРєР» checkout-Р·Р°РєР°Р·Р° Рё РµРіРѕ РїРѕР·РёС†РёР№."""

    async def calc_order_amount(self, session: AsyncSession, order: OrderORM) -> Decimal:
        items = await self.get_order_items(session, order.id)
        amount = Decimal("0")
        for order_item in items:
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            item_amount = await item_service.calc_amount()
            order_item.amount = item_amount
            order_item.updated_at = datetime.now(UTC)
            amount += Decimal(str(item_amount))

        if order.promocode_id is None or order.user_id is None:
            return amount
        if len(items) != 1:
            return amount

        first_item = items[0]
        first_handler = self.product_registry.get_handler_by_item_kind(first_item.kind)
        if first_handler is not None and first_handler.kind == "balance":
            return amount
        return await Promocode().calc_promocode_amount(
            session,
            order.promocode_id,
            order.user_id,
            first_item.product_id,
            order.currency,
            amount,
        )

    async def init_existing_order(
            self,
            session: AsyncSession,
            order: OrderORM,
            request_base_url: str,
            init_payment: bool,
    ) -> OrderDTO:
        if order.is_paid or order.payment_id:
            return await self.create_order_serializer().serialize_order(session, order)

        now = datetime.now(UTC)
        order.amount = await self.calc_order_amount(session, order)
        order.updated_at = now

        items = await self.get_order_items(session, order.id)
        for order_item in items:
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            await item_service.init(now)
            order_item.is_inited = True
            order_item.updated_at = now

        order.is_inited = True
        await session.flush()

        if not init_payment or Decimal(str(order.amount or 0)) <= 0 or not order.payment_system:
            return await self.create_order_serializer().serialize_order(session, order)

        self.validate_payment_system(order.currency, order.payment_system)
        payment = await self.create_payment_runtime().create(session, order, request_base_url)
        if payment is None:
            raise self.get_bad_request("Unknown payment system.")
        return await self.create_order_serializer().serialize_order(session, order)

    async def execute_order(self, session: AsyncSession, order: OrderORM) -> None:
        if order.is_executed:
            return
        if order.is_refunded:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The order cannot be processed because it has already been returned.",
            )

        now = datetime.now(UTC)
        items = await self.get_order_items(session, order.id)
        for order_item in items:
            if order_item.is_executed:
                continue
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            if not order_item.is_paid:
                order_item.is_paid = True
            await item_service.execute(now)
            order_item.is_executed = True
            order_item.updated_at = now

        if order.promocode_id is not None and order.user_id is not None:
            usage_query = select(PromocodeUsageORM.id).where(
                PromocodeUsageORM.promocode_id == order.promocode_id,
                PromocodeUsageORM.user_id == order.user_id,
            )
            usage_id = (await session.execute(usage_query)).scalar_one_or_none()
            if usage_id is None:
                session.add(
                    PromocodeUsageORM(
                        promocode_id=order.promocode_id,
                        user_id=order.user_id,
                        created_at=now,
                    ),
                )

        order.is_paid = True
        order.is_executed = True
        order.updated_at = now
        await session.flush()

    async def cancel_order(self, session: AsyncSession, order: OrderORM) -> None:
        if order.is_cancelled:
            return
        if order.is_paid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="To cancel a paid order and get a refund, please contact us.",
            )
        if order.is_refunded:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The order cannot be canceled because it refunded.",
            )
        if order.payment_id is not None:
            payment = await session.get(PaymentORM, order.payment_id)
            payment_service = self.payment_registry.get_service_by_kind(payment.kind) if payment is not None else None
            if payment_service is not None and payment_service.blocks_order_cancellation:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="To cancel a paid order and get a refund, please contact us.",
                )
        if order.is_executed:
            raise self.get_bad_request("Cannot cancel executed order.")

        now = datetime.now(UTC)
        order.is_cancelled = True
        order.updated_at = now
        for order_item in await self.get_order_items(session, order.id):
            order_item.is_cancelled = True
            order_item.updated_at = now
        await session.flush()

    async def revoke_order(self, session: AsyncSession, order: OrderORM) -> None:
        if order.is_refunded:
            return
        if not order.is_paid:
            raise self.get_bad_request("Cannot revoke unpaid order.")
        if not order.is_executed:
            raise self.get_bad_request("Cannot revoke unexecuted order.")

        now = datetime.now(UTC)
        for order_item in await self.get_order_items(session, order.id):
            if order_item.is_refunded:
                continue
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            if order_item.is_executed:
                await item_service.revoke(now)
            order_item.is_refunded = True
            order_item.updated_at = now

        order.is_refunded = True
        order.updated_at = now
        await session.flush()

    async def refund_order(self, session: AsyncSession, order: OrderORM) -> None:
        if order.is_refunded:
            return
        if not order.is_paid:
            raise self.get_bad_request("Cannot refund unpaid order.")

        await self.create_payment_runtime().refund(session, order)
        if order.is_executed:
            await self.revoke_order(session, order)
            return

        now = datetime.now(UTC)
        order.is_refunded = True
        order.updated_at = now
        for order_item in await self.get_order_items(session, order.id):
            order_item.is_refunded = True
            order_item.updated_at = now
        await session.flush()

    async def apply_product_effect(
            self,
            session: AsyncSession,
            *,
            user_id: int,
            product_id: int,
            currency: str,
            amount: Decimal,
            license_hours: int | None,
    ) -> None:
        product_kind = await self.get_product_kind(session, product_id)
        handler = self.product_registry.get_handler_by_kind(product_kind)
        if handler is None:
            return

        now = datetime.now(UTC)
        order = OrderORM(
            id=uuid4(),
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_system="",
            payment_id=None,
            promocode_id=None,
            is_inited=True,
            is_executed=False,
            is_paid=True,
            is_cancelled=False,
            is_refunded=False,
            kind="order",
            created_at=now,
            updated_at=now,
        )
        order_item = OrderItemORM(
            id=0,
            order_id=order.id,
            product_id=product_id,
            amount=amount,
            kind=handler.item_kinds[0],
            is_inited=True,
            is_executed=False,
            is_paid=True,
            is_cancelled=False,
            is_refunded=False,
            created_at=now,
            updated_at=now,
        )
        payload = {"license_hours": license_hours} if license_hours is not None else {}
        item_service = handler.create_order_item_service(order, order_item).bind(session)
        await item_service.create_item_record(payload, amount)
        await item_service.execute(now)


