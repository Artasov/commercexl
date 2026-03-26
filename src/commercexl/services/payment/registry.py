from __future__ import annotations

from typing import TYPE_CHECKING

from commercexl.services.payment.base import AbstractPaymentService

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime


class PaymentRegistry:
    """РҐСЂР°РЅРёС‚ СЃРµСЂРІРёСЃС‹ РѕРїР»Р°С‚ Рё Р±С‹СЃС‚СЂРѕ РЅР°С…РѕРґРёС‚ РЅСѓР¶РЅС‹Р№ РїРѕ `payment_system` РёР»Рё `payment.kind`."""

    def __init__(
            self,
            commerce: "BaseRuntime",
            service_classes: tuple[type[AbstractPaymentService], ...],
    ) -> None:
        self.services: tuple[AbstractPaymentService, ...] = tuple(
            service_class(commerce) for service_class in service_classes
        )
        self._services_by_system: dict[str, AbstractPaymentService] = {}
        self._services_by_kind: dict[str, AbstractPaymentService] = {}

        for service in self.services:
            normalized_system = self.normalize(service.payment_system)
            normalized_kind = self.normalize(service.payment_kind)
            if normalized_system:
                self._services_by_system.setdefault(normalized_system, service)
            if normalized_kind:
                self._services_by_kind.setdefault(normalized_kind, service)

    @staticmethod
    def normalize(value: str | None) -> str:
        return str(value or "").strip().lower()

    def get_service_by_system(self, payment_system: str | None) -> AbstractPaymentService | None:
        return self._services_by_system.get(self.normalize(payment_system))

    def get_service_by_kind(self, payment_kind: str | None) -> AbstractPaymentService | None:
        return self._services_by_kind.get(self.normalize(payment_kind))


