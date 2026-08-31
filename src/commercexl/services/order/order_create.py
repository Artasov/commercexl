from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, CreateOrderDTO
from commercexl.models import OrderItemORM, OrderORM, ProductORM
from commercexl.money import Money
from commercexl.order import OrderItemState, OrderState
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.idempotency import Idempotency
from commercexl.services.promocode.base import Promocode


class OrderCreate(BaseRuntime):
    """Первая checkout-фаза: server-priced заказ без создания payment attempt."""

    @staticmethod
    def get_global_payload_keys() -> set[str]:
        return {"currency", "promocode", "email", "products"}

    def get_product_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_products = payload.get("products")
        if raw_products is not None:
            if payload.get("product") not in {None, ""}:
                raise self.get_bad_request("Choose either product or products, not both.")
            if not isinstance(raw_products, list) or not raw_products:
                raise self.get_bad_request("Products must be a non-empty list.")
            return [dict(item) for item in raw_products]

        single_payload = {
            key: value
            for key, value in payload.items()
            if key not in self.get_global_payload_keys()
        }
        if single_payload.get("product") in {None, ""}:
            raise self.get_bad_request("Product is required.")
        return [single_payload]

    async def create_order(
            self,
            session: AsyncSession,
            actor: CommerceUserActorDTO,
            payload: dict[str, Any],
            idempotency_key: str,
    ) -> CreateOrderDTO:
        """Атомарно создаёт заказ или возвращает idempotent результат."""
        async with session.begin_nested():
            return await self._create_order(session, actor, payload, idempotency_key)

    async def _create_order(
            self,
            session: AsyncSession,
            actor: CommerceUserActorDTO,
            payload: dict[str, Any],
            idempotency_key: str,
    ) -> CreateOrderDTO:
        key = self._normalize_idempotency_key(idempotency_key)
        fingerprint = Idempotency.fingerprint(payload)
        existing = await self._get_idempotent_order(session, actor.id, key)
        if existing is not None:
            self._check_idempotency_fingerprint(existing.idempotency_fingerprint, fingerprint)
            return self._create_result(existing)

        product_payloads = self.get_product_payloads(payload)
        currency = self.get_config().normalize_currency(payload["currency"])
        self.get_available_payment_systems(currency)
        promocode_id = (
            self.parse_int(payload.get("promocode"), field_name="promocode")
            if payload.get("promocode") not in {None, ""}
            else None
        )
        if len(product_payloads) > 1 and promocode_id is not None:
            raise self.get_bad_request("Promocode is not supported for multi-product orders.")

        resolved_items: list[dict[str, Any]] = []
        for product_payload in product_payloads:
            product_id = self.parse_int(product_payload.get("product"), field_name="product")
            product: ProductORM | None = await session.get(ProductORM, product_id)
            if product is None:
                raise self.get_bad_request("Product not found.")

            product_kind = await self.get_product_kind(session, product_id)
            handler = self.product_registry.get_handler_by_kind(product_kind)
            if handler is None:
                raise self.get_bad_request("Unsupported product type.")

            await handler.can_create(session, product, product_payload)
            amount = Money.parse(await handler.get_price(session, product, currency, product_payload))
            if promocode_id is not None and handler.kind != "balance":
                amount = Money.parse(
                    await Promocode(commerce_module=self.commerce_module).calc_promocode_amount(
                        session,
                        promocode_id,
                        actor.id,
                        product_id,
                        currency,
                        amount,
                    ),
                )
            if amount < 0:
                raise self.get_bad_request("Order item amount cannot be negative.")
            resolved_items.append(
                {
                    "product_id": product_id,
                    "payload": product_payload,
                    "handler": handler,
                    "amount": amount,
                },
            )

        first_item_service_class = resolved_items[0]["handler"].get_order_item_service_class()
        handlers = tuple(item["handler"] for item in resolved_items)
        first_item_service_class.is_can_accept_product_services(handlers)
        if any(
                item["handler"].get_order_item_service_class() is not first_item_service_class
                for item in resolved_items
        ):
            raise self.get_bad_request("Products in one order must use the same order item service.")

        now = datetime.now(UTC)
        total_amount = Money.parse(sum((item["amount"] for item in resolved_items), start=Decimal("0")))
        order = OrderORM(
            id=uuid4(),
            user_id=actor.id,
            amount=total_amount,
            currency=currency,
            idempotency_key=key,
            idempotency_fingerprint=fingerprint,
            promocode_id=promocode_id,
            state=OrderState.CREATED.value,
            kind="order",
            created_at=now,
            updated_at=now,
        )
        inserted_order = await self._insert_order(session, order, actor.id, key, fingerprint)
        if inserted_order is not order:
            return self._create_result(inserted_order)

        item_services = []
        for item in resolved_items:
            order_item = OrderItemORM(
                order_id=order.id,
                product_id=item["product_id"],
                amount=item["amount"],
                kind=item["handler"].item_kinds[0],
                state=OrderItemState.CREATED.value,
                created_at=now,
                updated_at=now,
            )
            session.add(order_item)
            await session.flush()
            item_service = item["handler"].create_order_item_service(order, order_item).bind(session)
            item_record = await item_service.create_item_record(item["payload"], item["amount"])
            if item_record is not None:
                session.add(item_record)
            item_services.append(item_service)

        await session.flush()
        for item_service in item_services:
            await item_service.init(now)
            item_service.order_item.state = OrderItemState.READY.value
            item_service.order_item.updated_at = now

        order.state = OrderState.READY_FOR_PAYMENT.value
        order.updated_at = now
        await session.flush()

        if total_amount <= 0:
            await self.create_order_runtime().execute_order(session, order, payment=None)
        return self._create_result(order)

    async def _insert_order(
            self,
            session: AsyncSession,
            order: OrderORM,
            actor_id: int,
            key: str,
            fingerprint: str,
    ) -> OrderORM:
        try:
            async with session.begin_nested():
                session.add(order)
                await session.flush()
            return order
        except IntegrityError:
            existing = await self._get_idempotent_order(session, actor_id, key)
            if existing is None:
                raise
            self._check_idempotency_fingerprint(existing.idempotency_fingerprint, fingerprint)
            return existing

    @staticmethod
    async def _get_idempotent_order(
            session: AsyncSession,
            user_id: int,
            key: str,
    ) -> OrderORM | None:
        query = select(OrderORM).where(
            OrderORM.user_id == user_id,
            OrderORM.idempotency_key == key,
        )
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    def _create_result(order: OrderORM) -> CreateOrderDTO:
        return CreateOrderDTO(
            id=order.id,
            amount=Decimal(order.amount),
            currency=order.currency,
            state=order.order_state,
        )

    def _normalize_idempotency_key(self, value: str) -> str:
        try:
            return Idempotency.normalize_key(value)
        except ValueError as exc:
            raise self.get_bad_request(str(exc)) from exc

    def _check_idempotency_fingerprint(self, current: str, incoming: str) -> None:
        if current != incoming:
            raise self.get_conflict("Idempotency key was already used with a different payload.")
