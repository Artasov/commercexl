from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from commercexl.models import OrderItemORM, OrderORM

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime
    from commercexl.services.products.base import AbstractProductService


class AbstractOrderItemService(ABC):
    """Р‘Р°Р·РѕРІС‹Р№ СЃРµСЂРІРёСЃ РѕРґРЅРѕР№ РїРѕР·РёС†РёРё Р·Р°РєР°Р·Р°."""

    def __init__(
            self,
            commerce: "BaseRuntime",
            product_service: "AbstractProductService",
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: Any | None = None,
    ):
        self.commerce = commerce
        self.product_service = product_service
        self.order = order
        self.order_item = order_item
        self.item_record = item_record
        self._session = None

    async def create_item_record(self, payload: dict[str, Any], amount: Decimal) -> Any | None:
        _ = payload
        _ = amount
        if self.product_service.item_model is None:
            self.item_record = None
            return None
        self.item_record = self.product_service.item_model(order_item_id=self.order_item.id)
        return self.item_record

    async def calc_amount(self) -> Decimal:
        amount = await self.commerce.get_product_price(
            self.commerce_session,
            self.order_item.product_id,
            self.order.currency,
        )
        if amount is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product price not found.")
        return amount

    async def init(self, now: datetime) -> None:
        await self.product_service.pre_give(
            self.commerce_session,
            self.order,
            self.order_item,
            self.item_record,
            now,
        )

    async def execute(self, now: datetime) -> None:
        await self.product_service.post_give(
            self.commerce_session,
            self.order,
            self.order_item,
            self.item_record,
            now,
        )

    async def revoke(self, now: datetime) -> None:
        await self.product_service.revoke_give(
            self.commerce_session,
            self.order,
            self.order_item,
            self.item_record,
            now,
        )

    @property
    def commerce_session(self):
        return self._session

    def bind(self, session):
        self._session = session
        return self

    @classmethod
    def normalize_kind(cls, kind: str | None) -> str:
        return str(kind or "").strip().lower()

    @classmethod
    def can_accept_product_service(cls, product_service: "AbstractProductService") -> bool:
        accepted_product_kinds = getattr(cls, "accepted_product_kinds", ())
        if not accepted_product_kinds:
            return True
        return cls.normalize_kind(product_service.kind) in {
            cls.normalize_kind(value) for value in accepted_product_kinds
        }

    @classmethod
    def is_can_accept_product_services(cls, product_services: tuple["AbstractProductService", ...]) -> None:
        unsupported_kinds = [
            product_service.kind
            for product_service in product_services
            if not cls.can_accept_product_service(product_service)
        ]
        if unsupported_kinds:
            unsupported = ", ".join(sorted(set(unsupported_kinds)))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{cls.__name__} does not support products: {unsupported}.",
            )

    def get_product_id(self) -> int:
        return int(self.order_item.product_id)


class DefaultOrderItemService(AbstractOrderItemService):
    """Р‘Р°Р·РѕРІС‹Р№ item-service Р±РµР· СЃРІРѕРµР№ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕР№ Р»РѕРіРёРєРё."""

    pass


AbstractOrderService = AbstractOrderItemService
DefaultOrderService = DefaultOrderItemService


