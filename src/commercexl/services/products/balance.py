from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.models import BalanceOrderItemORM, BalanceProductORM, OrderItemORM, OrderORM, ProductORM
from commercexl.services.order.base import AbstractOrderItemService
from commercexl.services.pricing.credits import Credits
from commercexl.services.products.base import AbstractProductService


class BalanceOrderItemService(AbstractOrderItemService):
    """РЎРµСЂРІРёСЃ РїРѕР·РёС†РёРё РїРѕРїРѕР»РЅРµРЅРёСЏ Р±Р°Р»Р°РЅСЃР°."""

    async def create_item_record(self, payload: dict[str, Any], amount: Decimal) -> BalanceOrderItemORM:
        _ = payload
        self.item_record = BalanceOrderItemORM(
            order_item_id=self.order_item.id,
            requested_amount=amount,
            credited_amount=None,
        )
        return self.item_record

    async def calc_amount(self) -> Decimal:
        requested_amount = Decimal(str(self.item_record.requested_amount))
        self.commerce.validate_balance_top_up_amount(self.order.currency, requested_amount)
        return requested_amount


class BalanceProductService(AbstractProductService[BalanceOrderItemORM]):
    kind = "balance"
    product_kinds = ("balanceproduct", "balance")
    item_kinds = ("balanceproductitem", "balance")
    product_model = BalanceProductORM
    item_model = BalanceOrderItemORM

    async def can_create(self, session: AsyncSession, product: ProductORM, payload: dict[str, Any]) -> None:
        return None

    async def get_price(
            self,
            session: AsyncSession,
            product: ProductORM,
            currency: str,
            payload: dict[str, Any],
    ) -> Decimal:
        requested_amount = Decimal(str(payload.get("requested_amount") or "0"))
        if requested_amount <= 0: raise self.commerce.get_bad_request("requested_amount is required.")
        self.commerce.validate_balance_top_up_amount(currency, requested_amount)
        return requested_amount

    async def post_give(
            self,
            session: AsyncSession,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: BalanceOrderItemORM | None,
            now,
    ) -> None:
        if order.user_id is None or item_record is None or item_record.credited_amount is not None:
            return
        credits_amount = Credits.to_credits(
            self.commerce.get_config(),
            order.currency,
            Decimal(str(item_record.requested_amount)),
        )
        balance = await self.commerce.get_or_create_balance(session, order.user_id)
        balance.amount = Decimal(str(balance.amount)) + credits_amount
        balance.updated_at = now
        item_record.credited_amount = credits_amount


BalanceOrderService = BalanceOrderItemService


