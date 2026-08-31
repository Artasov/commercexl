from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime
    from commercexl.services.payment.base import AbstractPaymentService


PaymentProviderFactory = Callable[
    ["BaseRuntime", "PaymentProviderRegistration"],
    "AbstractPaymentService",
]


@dataclass(frozen=True)
class PaymentProviderRegistration:
    """Явно связывает provider identity с инъецируемой фабрикой."""

    system: str
    provider_kind: str
    factory: PaymentProviderFactory

    def __post_init__(self) -> None:
        normalized_system = PaymentRegistry.normalize(self.system)
        normalized_kind = PaymentRegistry.normalize(self.provider_kind)
        if not normalized_system:
            raise TypeError("Payment provider system cannot be empty.")
        if not normalized_kind:
            raise TypeError("Payment provider kind cannot be empty.")
        if len(normalized_system) > 50:
            raise TypeError("Payment provider system cannot exceed 50 characters.")
        if len(normalized_kind) > 100:
            raise TypeError("Payment provider kind cannot exceed 100 characters.")
        if not callable(self.factory):
            raise TypeError("Payment provider factory must be callable.")
        object.__setattr__(self, "system", normalized_system)
        object.__setattr__(self, "provider_kind", normalized_kind)

    def create_service(self, commerce: BaseRuntime) -> AbstractPaymentService:
        """Создаёт provider service через зарегистрированную фабрику."""
        service = self.factory(commerce, self)
        from commercexl.services.payment.base import AbstractPaymentService

        if not isinstance(service, AbstractPaymentService):
            raise TypeError("Payment provider factory must return AbstractPaymentService.")
        return service


class PaymentRegistry:
    """Хранит provider-ы с уникальной normalized identity."""

    def __init__(
            self,
            commerce: BaseRuntime,
            registrations: tuple[PaymentProviderRegistration, ...],
    ) -> None:
        self._services_by_system: dict[str, AbstractPaymentService] = {}
        self._services_by_identity: dict[tuple[str, str], AbstractPaymentService] = {}
        services: list[AbstractPaymentService] = []

        for registration in registrations:
            identity = (registration.system, registration.provider_kind)
            if registration.system in self._services_by_system:
                raise TypeError(f"Payment system '{registration.system}' is already registered.")
            if identity in self._services_by_identity:
                raise TypeError(f"Payment provider {identity!r} is already registered.")
            service = registration.create_service(commerce)
            services.append(service)
            self._services_by_system[registration.system] = service
            self._services_by_identity[identity] = service

        self.services = tuple(services)

    @staticmethod
    def normalize(value: str | None) -> str:
        """Нормализует provider identity для строгого сравнения."""
        return str(value or "").strip().lower()

    def get_service_by_system(self, payment_system: str | None) -> AbstractPaymentService | None:
        """Возвращает единственный provider зарегистрированной system."""
        return self._services_by_system.get(self.normalize(payment_system))

    def get_service(
            self,
            payment_system: str | None,
            provider_kind: str | None,
    ) -> AbstractPaymentService | None:
        """Ищет provider по полной immutable identity попытки."""
        return self._services_by_identity.get(
            (self.normalize(payment_system), self.normalize(provider_kind)),
        )
