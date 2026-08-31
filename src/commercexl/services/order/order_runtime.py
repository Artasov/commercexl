from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, OrderDTO
from commercexl.models import OrderItemORM, OrderORM, PaymentORM, PromocodeUsageORM
from commercexl.money import Money
from commercexl.order import OrderItemState, OrderState
from commercexl.payment import PaymentState
from commercexl.services.order.order_create import OrderCreate
from commercexl.services.promocode.base import Promocode


class OrderRuntime(OrderCreate):
    """Жизненный цикл заказа, вызываемый canonical payment runtime."""

    async def calc_order_amount(self, session: AsyncSession, order: OrderORM) -> Decimal:
        """Повторно рассчитывает server-side коммерческую сумму заказа."""
        items = await self.get_order_items(session, order.id)
        amount = Decimal("0")
        for order_item in items:
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            item_amount = Money.parse(await item_service.calc_amount())
            if item_amount < 0:
                raise self.get_bad_request("Order item amount cannot be negative.")
            order_item.amount = item_amount
            order_item.updated_at = datetime.now(UTC)
            amount += item_amount

        if order.promocode_id is None or order.user_id is None or len(items) != 1:
            return Money.parse(amount)
        first_handler = self.product_registry.get_handler_by_item_kind(items[0].kind)
        if first_handler is not None and first_handler.kind == "balance":
            return Money.parse(amount)
        discounted_amount = Money.parse(
            await Promocode(commerce_module=self.commerce_module).calc_promocode_amount(
                session,
                order.promocode_id,
                order.user_id,
                items[0].product_id,
                order.currency,
                amount,
            ),
        )
        if discounted_amount < 0:
            raise self.get_bad_request("Order amount cannot be negative.")
        return discounted_amount

    async def execute_order(
            self,
            session: AsyncSession,
            order: OrderORM,
            payment: PaymentORM | None,
    ) -> None:
        """Ровно один раз применяет product effects после paid либо для free order."""
        if order.order_state == OrderState.EXECUTED:
            return
        if order.order_state in {OrderState.CANCELLED, OrderState.REFUNDED}:
            raise self.get_conflict("Cancelled or refunded order cannot be executed.")
        if Decimal(order.amount) > 0:
            if (
                payment is None
                or payment.order_id != order.id
                or payment.payment_state != PaymentState.PAID
            ):
                raise self.get_conflict("Paid payment attempt is required to execute the order.")

        now = datetime.now(UTC)
        items = await self.get_order_items(session, order.id)
        for order_item in items:
            if order_item.item_state == OrderItemState.EXECUTED:
                continue
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            await item_service.execute(now)
            order_item.state = OrderItemState.EXECUTED.value
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

        order.state = OrderState.EXECUTED.value
        order.updated_at = now
        await session.flush()

    async def cancel_order(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> OrderDTO:
        """Атомарно отменяет active attempt через provider и затем заказ."""
        async with session.begin_nested():
            return await self._cancel_order(session, order_id, actor)

    async def _cancel_order(
            self,
            session: AsyncSession,
            order_id: str | UUID,
            actor: CommerceUserActorDTO,
    ) -> OrderDTO:
        order, _payment = await self.create_payment_runtime().cancel_for_order(
            session,
            order_id,
            actor,
        )
        if order.order_state == OrderState.CANCELLED:
            return await self.create_order_serializer().serialize_order(session, order)

        now = datetime.now(UTC)
        order.state = OrderState.CANCELLED.value
        order.updated_at = now
        for order_item in await self.get_order_items(session, order.id):
            order_item.state = OrderItemState.CANCELLED.value
            order_item.updated_at = now
        await session.flush()
        return await self.create_order_serializer().serialize_order(session, order)

    async def revoke_order(
            self,
            session: AsyncSession,
            order: OrderORM,
            payment: PaymentORM,
    ) -> None:
        """Отзывает product effects только после подтверждённого refund result."""
        if order.order_state == OrderState.REFUNDED:
            return
        if payment.order_id != order.id or payment.payment_state != PaymentState.REFUNDED:
            raise self.get_conflict("Refunded payment attempt is required to revoke the order.")
        if order.order_state != OrderState.EXECUTED:
            raise self.get_bad_request("Cannot revoke unpaid order.")

        now = datetime.now(UTC)
        for order_item in await self.get_order_items(session, order.id):
            if order_item.item_state == OrderItemState.REFUNDED:
                continue
            handler, _item_record, item_service = await self.get_order_item_payload(session, order_item)
            if handler is None or item_service is None:
                raise self.get_bad_request("Unknown order item.")
            if order_item.item_state == OrderItemState.EXECUTED:
                await item_service.revoke(now)
            order_item.state = OrderItemState.REFUNDED.value
            order_item.updated_at = now

        order.state = OrderState.REFUNDED.value
        order.updated_at = now
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
        """Применяет явно авторизованный host-side product effect вне checkout."""
        product_kind = await self.get_product_kind(session, product_id)
        handler = self.product_registry.get_handler_by_kind(product_kind)
        if handler is None:
            return

        now = datetime.now(UTC)
        order = OrderORM(
            id=uuid4(),
            user_id=user_id,
            amount=Money.parse(amount),
            currency=currency,
            idempotency_key=f"effect:{uuid4()}",
            idempotency_fingerprint="0" * 64,
            promocode_id=None,
            state=OrderState.EXECUTED.value,
            kind="order",
            created_at=now,
            updated_at=now,
        )
        order_item = OrderItemORM(
            id=0,
            order_id=order.id,
            product_id=product_id,
            amount=Money.parse(amount),
            kind=handler.item_kinds[0],
            state=OrderItemState.EXECUTED.value,
            created_at=now,
            updated_at=now,
        )
        payload = {"license_hours": license_hours} if license_hours is not None else {}
        item_service = handler.create_order_item_service(order, order_item).bind(session)
        await item_service.create_item_record(payload, amount)
        await item_service.execute(now)
