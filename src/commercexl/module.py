from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from commercexl.services.access import AbstractOrderAccessPolicy, OwnerOrderAccessPolicy
from commercexl.services.base_config import BaseConfig
from commercexl.services.payment.registry import PaymentProviderRegistration, PaymentRegistry


@dataclass(frozen=True, init=False)
class ProductOrderConfig:
    """Явная связка product-service и item-service для группы продуктов."""

    product_service_classes: tuple[type, ...]
    order_item_service_class: type | None = None

    def __init__(
            self,
            product_service_classes: type | tuple[type, ...],
            order_item_service_class: type | None = None,
    ) -> None:
        classes = product_service_classes if isinstance(product_service_classes, tuple) else (product_service_classes,)
        object.__setattr__(self, "product_service_classes", classes)
        object.__setattr__(self, "order_item_service_class", order_item_service_class)


class ProductOrderConfigBuilder:
    """Конфиг связок product и order item для commerce."""

    def __init__(
            self,
            *configs: ProductOrderConfig,
            serializer_class: type | None = None,
    ) -> None:
        self.configs: tuple[ProductOrderConfig, ...] = ()
        self.serializer_class = serializer_class or self.get_default_serializer_class()
        self.validate_serializer_class(self.serializer_class)
        if configs:
            self.add(*configs)

    @staticmethod
    def get_default_serializer_class() -> type:
        from commercexl.services.serialization.product import ProductSerializer
        return ProductSerializer

    @staticmethod
    def validate_serializer_class(serializer_class: type) -> None:
        from commercexl.services.serialization.product import ProductSerializer
        if not issubclass(serializer_class, ProductSerializer):
            raise TypeError(f"{serializer_class.__name__} must inherit from ProductSerializer.")

    @staticmethod
    def validate_product_service_class(service_class: type) -> None:
        from commercexl.services.products.base import AbstractProductService
        if not issubclass(service_class, AbstractProductService):
            raise TypeError(f"{service_class.__name__} must inherit from AbstractProductService.")

    @staticmethod
    def validate_order_item_service_class(service_class: type | None) -> None:
        if service_class is None:
            return
        from commercexl.services.order.base import AbstractOrderItemService
        if not issubclass(service_class, AbstractOrderItemService):
            raise TypeError(f"{service_class.__name__} must inherit from AbstractOrderItemService.")

    @classmethod
    def validate_config(cls, config: ProductOrderConfig) -> None:
        from commercexl.services.products.base import AbstractProductService

        if not config.product_service_classes:
            raise TypeError("ProductOrderConfig must contain at least one product service class.")
        for product_service_class in config.product_service_classes:
            cls.validate_product_service_class(product_service_class)
        cls.validate_order_item_service_class(config.order_item_service_class)

        for product_service_class in config.product_service_classes:
            uses_default_factory = (
                product_service_class.create_order_item_service is AbstractProductService.create_order_item_service
            )
            has_default_item_service = getattr(
                product_service_class,
                "default_order_item_service_class",
                None,
            ) is not None
            if config.order_item_service_class is None and uses_default_factory and not has_default_item_service:
                raise TypeError(
                    f"{product_service_class.__name__} requires an explicit order item service class "
                    "in ProductOrderConfig.",
                )

    @staticmethod
    def validate_unique_products(configs: tuple[ProductOrderConfig, ...]) -> None:
        used_product_service_classes: dict[type, ProductOrderConfig] = {}
        for config in configs:
            for product_service_class in config.product_service_classes:
                if product_service_class in used_product_service_classes:
                    raise TypeError(
                        f"{product_service_class.__name__} is already registered in another ProductOrderConfig.",
                    )
                used_product_service_classes[product_service_class] = config

    def add(self, *configs: ProductOrderConfig) -> ProductOrderConfigBuilder:
        for config in configs:
            self.validate_config(config)
        items = list(self.configs)
        for config in configs:
            if config not in items:
                items.append(config)
        self.configs = tuple(items)
        self.validate_unique_products(self.configs)
        return self


class OrderRuntimeConfigBuilder:
    """Конфиг общего order runtime и serializer."""

    def __init__(
            self,
            *,
            runtime_class: type | None = None,
            serializer_class: type | None = None,
    ) -> None:
        self.runtime_class = runtime_class or self.get_default_runtime_class()
        self.serializer_class = serializer_class or self.get_default_serializer_class()
        self.validate_runtime_class(self.runtime_class)
        self.validate_serializer_class(self.serializer_class)

    @staticmethod
    def get_default_runtime_class() -> type:
        from commercexl.services.order.order_runtime import OrderRuntime
        return OrderRuntime

    @staticmethod
    def get_default_serializer_class() -> type:
        from commercexl.services.serialization.order import OrderSerializer
        return OrderSerializer

    @staticmethod
    def validate_runtime_class(runtime_class: type) -> None:
        from commercexl.services.order.order_runtime import OrderRuntime
        if not issubclass(runtime_class, OrderRuntime):
            raise TypeError(f"{runtime_class.__name__} must inherit from OrderRuntime.")

    @staticmethod
    def validate_serializer_class(serializer_class: type) -> None:
        from commercexl.services.serialization.order import OrderSerializer
        if not issubclass(serializer_class, OrderSerializer):
            raise TypeError(f"{serializer_class.__name__} must inherit from OrderSerializer.")


class PaymentConfigBuilder:
    """Строгий конфиг payment registrations и runtime."""

    def __init__(
            self,
            *registrations: PaymentProviderRegistration,
            runtime_class: type | None = None,
            serializer_class: type | None = None,
    ) -> None:
        self.registrations: tuple[PaymentProviderRegistration, ...] = ()
        self.runtime_class = runtime_class or self.get_default_runtime_class()
        self.serializer_class = serializer_class or self.get_default_serializer_class()
        self.validate_runtime_class(self.runtime_class)
        self.validate_serializer_class(self.serializer_class)
        if registrations:
            self.add(*registrations)

    @staticmethod
    def get_default_runtime_class() -> type:
        from commercexl.services.payment.payment_runtime import PaymentRuntime
        return PaymentRuntime

    @staticmethod
    def get_default_serializer_class() -> type:
        from commercexl.services.serialization.payment import PaymentSerializer
        return PaymentSerializer

    @staticmethod
    def validate_runtime_class(runtime_class: type) -> None:
        from commercexl.services.payment.payment_runtime import PaymentRuntime
        if not issubclass(runtime_class, PaymentRuntime):
            raise TypeError(f"{runtime_class.__name__} must inherit from PaymentRuntime.")

    @staticmethod
    def validate_serializer_class(serializer_class: type) -> None:
        from commercexl.services.serialization.payment import PaymentSerializer
        if not issubclass(serializer_class, PaymentSerializer):
            raise TypeError(f"{serializer_class.__name__} must inherit from PaymentSerializer.")

    @staticmethod
    def validate_registration(registration: PaymentProviderRegistration) -> None:
        if not isinstance(registration, PaymentProviderRegistration):
            raise TypeError("PaymentConfigBuilder accepts PaymentProviderRegistration values only.")

    def add(self, *registrations: PaymentProviderRegistration) -> PaymentConfigBuilder:
        systems = {registration.system for registration in self.registrations}
        identities = {
            (registration.system, registration.provider_kind)
            for registration in self.registrations
        }
        items = list(self.registrations)
        for registration in registrations:
            self.validate_registration(registration)
            identity = (registration.system, registration.provider_kind)
            if registration.system in systems:
                raise TypeError(f"Payment system '{registration.system}' is already registered.")
            if identity in identities:
                raise TypeError(f"Payment provider {identity!r} is already registered.")
            systems.add(registration.system)
            identities.add(identity)
            items.append(registration)
        self.registrations = tuple(items)
        return self

    def get_registered_systems(self) -> set[str]:
        return {registration.system for registration in self.registrations}


class CommerceModule:
    """Явная точка подключения commerce к host-приложению."""

    def __init__(
            self,
            *,
            config_class: type[BaseConfig] = BaseConfig,
            product_orders: ProductOrderConfigBuilder | None = None,
            order_runtime: OrderRuntimeConfigBuilder | None = None,
            payments: PaymentConfigBuilder | None = None,
            order_access_policy: AbstractOrderAccessPolicy | None = None,
            public_base_url: str | None = None,
    ) -> None:
        self.config_class = config_class
        self.product_orders = product_orders or ProductOrderConfigBuilder()
        self.order_runtime = order_runtime or OrderRuntimeConfigBuilder()
        self.payments = payments or PaymentConfigBuilder()
        self.order_access_policy = order_access_policy or OwnerOrderAccessPolicy()
        self.public_base_url = self.normalize_public_base_url(public_base_url)
        self.config_class.validate()
        self.validate_payment_systems()

    @staticmethod
    def normalize_public_base_url(value: str | None) -> str | None:
        """Принимает только явно настроенный HTTP origin, не request Host."""
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        try:
            parsed.port
        except ValueError as exc:
            raise TypeError("public_base_url has an invalid port.") from exc
        if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
        ):
            raise TypeError("public_base_url must be an absolute HTTP origin without a path.")
        return normalized

    def validate_payment_systems(self) -> None:
        registered_systems = self.payments.get_registered_systems()
        if not registered_systems:
            raise TypeError("CommerceModule requires at least one payment provider registration.")
        for currency, payment_systems in self.config_class.get_payment_systems_map().items():
            for payment_system in payment_systems:
                normalized_system = PaymentRegistry.normalize(payment_system)
                if normalized_system not in registered_systems:
                    raise TypeError(
                        f"{self.config_class.__name__}.PAYMENT_SYSTEMS[{currency}] contains "
                        f"'{payment_system}', but this provider is not registered.",
                    )

    def create_base_runtime(self):
        from commercexl.services.base_runtime import BaseRuntime
        return BaseRuntime(commerce_module=self)

    def create_order_runtime(self):
        return self.order_runtime.runtime_class(commerce_module=self)

    def create_payment_runtime(self):
        return self.payments.runtime_class(commerce_module=self)

    def create_order_serializer(self):
        return self.order_runtime.serializer_class(commerce_module=self)

    def create_payment_serializer(self):
        return self.payments.serializer_class(commerce_module=self)

    def create_product_serializer(self):
        return self.product_orders.serializer_class(commerce_module=self)


@lru_cache(maxsize=1)
def get_default_commerce_module() -> CommerceModule:
    from commercexl.services.payment.balance import BalancePaymentService
    from commercexl.services.payment.handmade import HandMadePaymentService
    from commercexl.services.products.balance import BalanceOrderItemService, BalanceProductService

    return CommerceModule(
        config_class=BaseConfig,
        product_orders=ProductOrderConfigBuilder(
            ProductOrderConfig(BalanceProductService, BalanceOrderItemService),
        ),
        order_runtime=OrderRuntimeConfigBuilder(),
        payments=PaymentConfigBuilder(
            PaymentProviderRegistration("handmade", "handmade", HandMadePaymentService),
            PaymentProviderRegistration("balance", "balance", BalancePaymentService),
        ),
    )
