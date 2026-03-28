from __future__ import annotations

from abc import ABC
from decimal import Decimal
from inspect import isabstract
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.models import OrderItemORM, OrderORM, ProductORM
from commercexl.services.order.base import AbstractOrderItemService

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime

ItemRecordT = TypeVar("ItemRecordT")


class AbstractProductService(ABC, Generic[ItemRecordT]):
    """Абстрактный сервис конкретного вида продукта внутри `commerce`."""

    kind: str = ""
    product_kinds: tuple[str, ...] = ()
    item_kinds: tuple[str, ...] = ()
    product_model: type[Any] | None = None
    item_model: type[ItemRecordT] | None = None
    default_order_item_service_class: type[AbstractOrderItemService] | None = None
    __skip_product_validation__: bool = False

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if isabstract(cls) or cls.__dict__.get("__skip_product_validation__", False):
            return
        if not str(getattr(cls, "kind", "")).strip():
            raise TypeError(f"{cls.__name__} must define 'kind'.")
        if not tuple(getattr(cls, "product_kinds", ())):
            raise TypeError(f"{cls.__name__} must define 'product_kinds'.")
        if not tuple(getattr(cls, "item_kinds", ())):
            raise TypeError(f"{cls.__name__} must define 'item_kinds'.")
        order_item_service_class = getattr(cls, "default_order_item_service_class", None)
        if order_item_service_class is not None and not issubclass(
                order_item_service_class, AbstractOrderItemService,
        ):
            raise TypeError(
                f"{cls.__name__}.default_order_item_service_class must inherit from AbstractOrderItemService.",
            )

    def __init__(
            self,
            commerce: "BaseRuntime",
            order_item_service_class: type[AbstractOrderItemService] | None = None,
    ) -> None:
        self.commerce = commerce
        self._order_item_service_class = order_item_service_class

    def create_order_item_service(
            self,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: ItemRecordT | None = None,
    ) -> AbstractOrderItemService:
        order_item_service_class = self.get_order_item_service_class()
        return order_item_service_class(self.commerce, self, order, order_item, item_record)

    def get_order_item_service_class(self) -> type[AbstractOrderItemService]:
        if self._order_item_service_class is not None:
            return self._order_item_service_class
        if self.default_order_item_service_class is not None:
            return self.default_order_item_service_class
        raise TypeError(
            f"{self.__class__.__name__} has no order item service class. "
            f"Register it in CommerceModule via ProductOrderConfig or define default_order_item_service_class.",
        )

    async def can_create(self, session: AsyncSession, product: ProductORM, payload: dict[str, Any]) -> None:
        if not product.is_available:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is not available.")

    async def get_price(
            self,
            session: AsyncSession,
            product: ProductORM,
            currency: str,
            payload: dict[str, Any],
    ) -> Decimal:
        amount = await self.commerce.get_product_price(session, product.id, currency)
        if amount is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product price not found.")
        return amount

    async def pre_give(
            self,
            session: AsyncSession,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: ItemRecordT | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        _ = item_record
        _ = now
        return None

    async def post_give(
            self,
            session: AsyncSession,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: ItemRecordT | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        _ = item_record
        _ = now
        return None

    async def revoke_give(
            self,
            session: AsyncSession,
            order: OrderORM,
            order_item: OrderItemORM,
            item_record: ItemRecordT | None,
            now,
    ) -> None:
        _ = session
        _ = order
        _ = order_item
        _ = item_record
        _ = now
        return None

    def has_product_kind(self, kind: str | None) -> bool:
        normalized = str(kind or "").strip().lower()
        return normalized in {value.lower() for value in self.product_kinds}

    def has_item_kind(self, kind: str | None) -> bool:
        normalized = str(kind or "").strip().lower()
        return normalized in {value.lower() for value in self.item_kinds}

    async def get_product_record(self, session: AsyncSession, product_id: int) -> Any | None:
        if self.product_model is None:
            return None
        return await session.get(self.product_model, product_id)

    async def get_item_record(self, session: AsyncSession, order_item_id: int) -> ItemRecordT | None:
        if self.item_model is None:
            return None
        return await session.get(self.item_model, order_item_id)


class DefaultProductService(AbstractProductService[ItemRecordT], ABC):
    """Простейшая база для продукта без своей логики."""

    __skip_product_validation__ = True


