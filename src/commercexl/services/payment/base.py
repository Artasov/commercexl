from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from inspect import isabstract
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO
from commercexl.models import OrderORM, PaymentORM

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime


class AbstractPaymentService(ABC):
    """Абстрактный сервис одного способа оплаты внутри `commerce`."""

    payment_system: str = ""
    payment_kind: str = ""
    blocks_order_cancellation = False

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if isabstract(cls):
            return
        if not str(getattr(cls, "payment_system", "")).strip():
            raise TypeError(f"{cls.__name__} must define 'payment_system'.")
        if not str(getattr(cls, "payment_kind", "")).strip():
            raise TypeError(f"{cls.__name__} must define 'payment_kind'.")

    def __init__(self, commerce: "BaseRuntime") -> None:
        self.commerce = commerce

    @abstractmethod
    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            amount: Decimal,
            request_base_url: str,
    ) -> PaymentORM:
        raise NotImplementedError

    @abstractmethod
    async def is_paid(self, session: AsyncSession, payment_id: int) -> bool:
        raise NotImplementedError

    async def refund(self, session: AsyncSession, order: OrderORM, payment: PaymentORM) -> None:
        _ = session
        _ = order
        _ = payment
        raise self.commerce.get_bad_request("Payment refund is not supported.")

    async def create_parent_payment(
            self,
            session: AsyncSession,
            *,
            order: OrderORM,
            amount: Decimal,
            is_paid: bool,
            payment_url: str | None,
    ) -> PaymentORM:
        payment = PaymentORM(
            user_id=order.user_id,
            amount=amount,
            currency=order.currency,
            payment_url=payment_url,
            is_paid=is_paid,
            kind=self.payment_kind,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(payment)
        await session.flush()
        return payment

    def has_payment_system(self, payment_system: str | None) -> bool:
        normalized_system = str(payment_system or "").strip().lower()
        return normalized_system == self.payment_system.lower()

    def has_payment_kind(self, payment_kind: str | None) -> bool:
        normalized_kind = str(payment_kind or "").strip().lower()
        return normalized_kind == self.payment_kind.lower()

    async def get_extras(self, session: AsyncSession, payment_id: int) -> dict[str, Any] | None:
        _ = session
        _ = payment_id
        return None

    async def get_pay_link(self, session: AsyncSession, payment_id: int) -> str | None:
        payment = await session.get(PaymentORM, payment_id)
        return str(payment.payment_url) if payment and payment.payment_url is not None else None

    async def finalize_paid_order(self, session: AsyncSession, order: OrderORM) -> OrderDTO:
        """
        Идемпотентно завершает заказ после успешной оплаты.

        Повторный callback или повторная ручная проверка не должны
        повторно выполнять заказ. Поэтому здесь:
        - оплата помечается успешной только один раз;
        - `execute_order()` вызывается только если заказ ещё не выполнен;
        - в ответ всегда возвращается актуальный `OrderDTO`.
        """
        if order.is_cancelled:
            return await self.commerce.create_order_serializer().serialize_order(session, order)

        if not order.is_paid:
            order.is_paid = True
            order.updated_at = datetime.now(UTC)

        if not order.is_executed and not order.is_refunded:
            await self.commerce.create_order_runtime().execute_order(session, order)

        await session.flush()
        return await self.commerce.create_order_serializer().serialize_order(session, order)


class AbstractCallbackPaymentService(AbstractPaymentService, ABC):
    """Базовый сервис оплаты, у которой есть callback или ручная проверка."""

    @abstractmethod
    async def confirm(self, session: AsyncSession, data: dict[str, Any]) -> OrderDTO:
        raise NotImplementedError

    @abstractmethod
    async def check(self, session: AsyncSession, data: dict[str, Any]) -> OrderDTO:
        raise NotImplementedError


