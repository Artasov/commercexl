from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO
from commercexl.models import OrderORM, PaymentORM
from commercexl.payment import (
    CheckoutAction,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentVerificationResult,
)

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime
    from commercexl.services.payment.registry import PaymentProviderRegistration


class AbstractPaymentService(ABC):
    """Provider adapter, который не меняет заказ и canonical attempt напрямую."""

    def __init__(
            self,
            commerce: BaseRuntime,
            registration: PaymentProviderRegistration,
    ) -> None:
        self.commerce = commerce
        self.registration = registration

    @property
    def payment_system(self) -> str:
        """Возвращает system из строгой регистрации."""
        return self.registration.system

    @property
    def provider_kind(self) -> str:
        """Возвращает kind дочерней provider-модели."""
        return self.registration.provider_kind

    @abstractmethod
    async def list_options(
            self,
            session: AsyncSession,
            order: OrderORM,
            actor: CommerceUserActorDTO,
    ) -> tuple[PaymentOption, ...]:
        """Публикует варианты, реально доступные этому actor и заказу."""
        raise NotImplementedError

    @abstractmethod
    async def create(
            self,
            session: AsyncSession,
            context: PaymentCreateContext,
    ) -> PaymentCreateResult:
        """Создаёт только provider child/evidence и возвращает typed action."""
        raise NotImplementedError

    @abstractmethod
    async def get_action(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> CheckoutAction:
        """Выпускает action без сохранения bearer capability в canonical attempt."""
        raise NotImplementedError

    @abstractmethod
    async def cancel(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> PaymentVerificationResult:
        """Отменяет provider-side intent либо подтверждает локальную отмену."""
        raise NotImplementedError

    async def refund(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> PaymentVerificationResult:
        """Запрашивает возврат; success должен быть подтверждён typed result."""
        _ = session
        _ = payment
        raise self.commerce.get_bad_request("Payment refund is not supported.")


class AbstractCallbackPaymentService(AbstractPaymentService, ABC):
    """Provider, который преобразует callback/check в typed verification result."""

    @abstractmethod
    async def verify(
            self,
            session: AsyncSession,
            payment: PaymentORM,
            payload: object,
    ) -> PaymentVerificationResult:
        """Проверяет provider evidence, не исполняя заказ."""
        raise NotImplementedError
