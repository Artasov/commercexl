from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, CreateOrderDTO, CreateOrderIdOnlyDTO
from commercexl.models import OrderItemORM, OrderORM, ProductORM
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.promocode.base import Promocode


class OrderCreate(BaseRuntime):
    """РЎРѕР·РґР°РЅРёРµ checkout-Р·Р°РєР°Р·Р° Рё РµРіРѕ РїРѕР·РёС†РёР№."""

    @staticmethod
    def get_global_payload_keys() -> set[str]:
        return {"currency", "payment_system", "promocode", "email", "products"}

    def get_product_payloads(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_products = payload.get("products")
        if raw_products is not None:
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
            request_base_url: str,
    ) -> CreateOrderIdOnlyDTO | CreateOrderDTO:
        product_payloads = self.get_product_payloads(payload)
        currency = payload["currency"]
        payment_system = payload["payment_system"]
        self.validate_payment_system(currency, payment_system)
        promocode_id = self.parse_int(payload.get("promocode"), field_name="promocode") if payload.get(
            "promocode",
        ) not in {None, ""} else None
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
            amount = await handler.get_price(session, product, currency, product_payload)
            if promocode_id is not None and handler.kind != "balance":
                amount = await Promocode().calc_promocode_amount(
                    session, promocode_id, actor.id, product_id, currency, amount,
                )

            resolved_items.append(
                {
                    "product_id": product_id,
                    "payload": product_payload,
                    "handler": handler,
                    "amount": Decimal(str(amount)),
                },
            )

        first_handler = resolved_items[0]["handler"]
        first_item_service_class = first_handler.get_order_item_service_class()
        handlers = tuple(item["handler"] for item in resolved_items)
        first_item_service_class.is_can_accept_product_services(handlers)
        if any(
                item["handler"].get_order_item_service_class() is not first_item_service_class
                for item in resolved_items
        ):
            raise self.get_bad_request("Products in one order must use the same order item service.")

        now = datetime.now(UTC)
        total_amount = sum((item["amount"] for item in resolved_items), start=Decimal("0"))
        order = OrderORM(
            id=uuid4(),
            user_id=actor.id,
            amount=total_amount,
            currency=currency,
            payment_system=payment_system,
            payment_id=None,
            promocode_id=promocode_id,
            is_inited=False,
            is_executed=False,
            is_paid=False,
            is_cancelled=False,
            is_refunded=False,
            kind="order",
            created_at=now,
            updated_at=now,
        )
        session.add(order)
        await session.flush()

        item_services = []
        for item in resolved_items:
            order_item = OrderItemORM(
                order_id=order.id,
                product_id=item["product_id"],
                amount=item["amount"],
                kind=item["handler"].item_kinds[0],
                is_inited=False,
                is_executed=False,
                is_paid=False,
                is_cancelled=False,
                is_refunded=False,
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
            item_service.order_item.is_inited = True
            item_service.order_item.updated_at = now

        order.is_inited = True
        order.updated_at = now
        await session.flush()

        if total_amount <= 0:
            return CreateOrderIdOnlyDTO(id=str(order.id))

        payment = await self.create_payment_runtime().create(session, order, request_base_url)
        if payment is None:
            raise self.get_bad_request("Unknown payment system.")
        return CreateOrderDTO(payment_url=payment.payment_url, id=str(order.id))


