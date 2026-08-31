from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, PromocodeDTO
from commercexl.models import OrderItemORM, OrderORM, ProductORM, ProductPriceORM, UserCreditsBalanceORM
from commercexl.module import get_default_commerce_module
from commercexl.services.access import OrderAccessAction
from commercexl.services.base_config import BaseConfig
from commercexl.services.payment.registry import PaymentRegistry
from commercexl.services.products.registry import Registry


class BaseRuntime:
    """Общая инфраструктура commerce: registry, lookups и access policy."""

    config_class = BaseConfig

    def __init__(
            self,
            *,
            commerce_module=None,
            product_registry: Registry | None = None,
            payment_registry: PaymentRegistry | None = None,
    ) -> None:
        self.commerce_module = commerce_module or get_default_commerce_module()
        self._product_registry = product_registry or self.create_product_registry()
        self._payment_registry = payment_registry or self.create_payment_registry()

    def create_product_registry(self) -> Registry:
        return Registry(self, configs=self.commerce_module.product_orders.configs)

    def create_payment_registry(self) -> PaymentRegistry:
        self.commerce_module.validate_payment_systems()
        return PaymentRegistry(self, registrations=self.commerce_module.payments.registrations)

    @property
    def product_registry(self) -> Registry:
        return self._product_registry

    @property
    def payment_registry(self) -> PaymentRegistry:
        return self._payment_registry

    def get_config(self) -> type[BaseConfig]:
        return self.commerce_module.config_class if self.commerce_module is not None else self.config_class

    def create_order_runtime(self):
        return self.commerce_module.create_order_runtime()

    def create_payment_runtime(self):
        return self.commerce_module.create_payment_runtime()

    def create_order_serializer(self):
        return self.commerce_module.create_order_serializer()

    def create_payment_serializer(self):
        return self.commerce_module.create_payment_serializer()

    @staticmethod
    def get_bad_request(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    @staticmethod
    def get_not_found(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    @staticmethod
    def get_conflict(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    @staticmethod
    def parse_int(value: Any, *, field_name: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is invalid.") from exc

    @staticmethod
    async def get_or_create_balance(session: AsyncSession, user_id: int) -> UserCreditsBalanceORM:
        query = select(UserCreditsBalanceORM).where(UserCreditsBalanceORM.user_id == user_id)
        balance = (await session.execute(query)).scalar_one_or_none()
        if balance is None:
            now = datetime.now(UTC)
            balance = UserCreditsBalanceORM(
                user_id=user_id,
                amount=Decimal("0"),
                created_at=now,
                updated_at=now,
            )
            session.add(balance)
            await session.flush()
        return balance

    @staticmethod
    async def get_balance(session: AsyncSession, user_id: int) -> UserCreditsBalanceORM | None:
        query = select(UserCreditsBalanceORM).where(UserCreditsBalanceORM.user_id == user_id)
        return (await session.execute(query)).scalar_one_or_none()

    @staticmethod
    def normalize_order_id(order_id: str | UUID) -> UUID | None:
        try:
            return order_id if isinstance(order_id, UUID) else UUID(str(order_id))
        except (TypeError, ValueError):
            return None

    @classmethod
    async def get_order(cls, session: AsyncSession, order_id: str | UUID) -> OrderORM | None:
        normalized_id = cls.normalize_order_id(order_id)
        return await session.get(OrderORM, normalized_id) if normalized_id is not None else None

    @classmethod
    async def get_order_for_update(cls, session: AsyncSession, order_id: str | UUID) -> OrderORM | None:
        """Блокирует заказ первым во всех payment mutation flows."""
        normalized_id = cls.normalize_order_id(order_id)
        if normalized_id is None:
            return None
        query = (
            select(OrderORM)
            .where(OrderORM.id == normalized_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await session.execute(query)).scalar_one_or_none()

    async def refresh_order(self, session: AsyncSession, order_id: str | UUID) -> OrderORM:
        order = await self.get_order(session, order_id)
        if order is None:
            raise self.get_not_found("Order not found.")
        await session.refresh(order)
        return order

    async def check_order_access(
            self,
            session: AsyncSession,
            actor: CommerceUserActorDTO,
            order: OrderORM,
            action: OrderAccessAction,
    ) -> None:
        """Скрывает чужой заказ за 404 независимо от способа вызова runtime."""
        is_allowed = await self.commerce_module.order_access_policy.is_allowed(
            session,
            actor,
            order,
            action,
        )
        if not is_allowed:
            raise self.get_not_found("Order not found.")

    def get_available_payment_systems(self, currency: str) -> tuple[str, ...]:
        config = self.get_config()
        normalized_currency = config.normalize_currency(currency)
        payment_systems = config.get_payment_systems_map().get(normalized_currency)
        if payment_systems is None:
            raise self.get_bad_request("Currency not supported.")
        return tuple(PaymentRegistry.normalize(system) for system in payment_systems)

    def validate_payment_system(self, currency: str, payment_system: str) -> None:
        if PaymentRegistry.normalize(payment_system) not in self.get_available_payment_systems(currency):
            raise self.get_bad_request("Currency not supported for payment system.")

    def validate_balance_top_up_amount(self, currency: str, requested_amount: Decimal) -> None:
        config = self.get_config()
        min_amount = config.get_min_top_up_amount(currency)
        if requested_amount < min_amount:
            raise self.get_bad_request(f"Minimum amount for {currency} is {min_amount}")
        if requested_amount > config.MAX_TOP_UP_AMOUNT:
            raise self.get_bad_request(f"Maximum amount is {config.MAX_TOP_UP_AMOUNT}")

    @staticmethod
    async def get_price_row(session: AsyncSession, product_id: int, currency: str) -> ProductPriceORM | None:
        query = select(ProductPriceORM).where(
            ProductPriceORM.product_id == product_id,
            ProductPriceORM.currency == currency,
        ).limit(1)
        return (await session.execute(query)).scalar_one_or_none()

    async def get_product_price(self, session: AsyncSession, product_id: int, currency: str) -> Decimal | None:
        price = await self.get_price_row(session, product_id, currency)
        return Decimal(price.amount) if price is not None else None

    async def get_product_kind(self, session: AsyncSession, product_id: int) -> str | None:
        product = await session.get(ProductORM, product_id)
        if product is None:
            return None
        handler = self.product_registry.get_handler_by_product_kind(str(product.kind))
        return handler.kind if handler is not None else None

    @staticmethod
    async def get_order_items(session: AsyncSession, order_id: UUID) -> list[OrderItemORM]:
        query = (
            select(OrderItemORM)
            .where(OrderItemORM.order_id == order_id)
            .order_by(OrderItemORM.created_at.asc(), OrderItemORM.id.asc())
        )
        return list((await session.execute(query)).scalars())

    @staticmethod
    async def get_order_item(session: AsyncSession, order_item_id: int) -> OrderItemORM | None:
        return await session.get(OrderItemORM, order_item_id)

    async def get_order_item_payload(
            self,
            session: AsyncSession,
            order_item: OrderItemORM,
    ) -> tuple[Any | None, Any | None, Any | None]:
        handler = self.product_registry.get_handler_by_item_kind(order_item.kind)
        if handler is None:
            return None, None, None
        item_record = await handler.get_item_record(session, order_item.id)
        order = await session.get(OrderORM, order_item.order_id)
        item_service = handler.create_order_item_service(order, order_item, item_record).bind(session)
        return handler, item_record, item_service

    async def serialize_promocode(self, session: AsyncSession, promocode_id: int | None) -> PromocodeDTO | None:
        raise NotImplementedError
