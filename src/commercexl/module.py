from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from commercexl.services.base_config import BaseConfig


def _merge_unique_classes(current: tuple[type, ...], new_items: tuple[type, ...]) -> tuple[type, ...]:
    items = list(current)
    for item in new_items:
        if item not in items:
            items.append(item)
    return tuple(items)


@dataclass(frozen=True, init=False)
class ProductOrderConfig:
    """РЇРІРЅР°СЏ СЃРІСЏР·РєР° product-service Рё item-service РґР»СЏ РѕРґРЅРѕРіРѕ РїСЂРѕРґСѓРєС‚Р° РёР»Рё РіСЂСѓРїРїС‹ РїСЂРѕСЃС‚С‹С… РїСЂРѕРґСѓРєС‚РѕРІ."""

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
    """РљРѕРЅС„РёРі СЃРІСЏР·РѕРє `product + order item` РґР»СЏ `commerce`."""

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
                product_service_class, "default_order_item_service_class", None,
            ) is not None
            if config.order_item_service_class is None and uses_default_factory and not has_default_item_service:
                raise TypeError(
                    f"{product_service_class.__name__} requires an explicit order item service class in ProductOrderConfig.",
                )

    @staticmethod
    def validate_unique_products(configs: tuple[ProductOrderConfig, ...]) -> None:
        used_product_service_classes: dict[type, ProductOrderConfig] = {}
        for config in configs:
            for product_service_class in config.product_service_classes:
                existing_config = used_product_service_classes.get(product_service_class)
                if existing_config is not None:
                    raise TypeError(
                        f"{product_service_class.__name__} is already registered in another ProductOrderConfig.",
                    )
                used_product_service_classes[product_service_class] = config

    def add(self, *configs: ProductOrderConfig) -> ProductOrderConfigBuilder:
        for config in configs:
            self.validate_config(config)
        self.configs = _merge_unique_classes(self.configs, configs)
        self.validate_unique_products(self.configs)
        return self


class OrderRuntimeConfigBuilder:
    """РљРѕРЅС„РёРі РѕР±С‰РµРіРѕ order runtime Рё serializer РґР»СЏ `commerce`."""

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
    """РљРѕРЅС„РёРі payment-service РєР»Р°СЃСЃРѕРІ `commerce`."""

    def __init__(
            self,
            *service_classes: type,
            runtime_class: type | None = None,
            serializer_class: type | None = None,
    ) -> None:
        self.service_classes: tuple[type, ...] = ()
        self.runtime_class = runtime_class or self.get_default_runtime_class()
        self.serializer_class = serializer_class or self.get_default_serializer_class()
        self.validate_runtime_class(self.runtime_class)
        self.validate_serializer_class(self.serializer_class)
        if service_classes:
            self.add(*service_classes)

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
    def validate_service_class(service_class: type) -> None:
        from commercexl.services.payment.base import AbstractPaymentService
        if not issubclass(service_class, AbstractPaymentService):
            raise TypeError(f"{service_class.__name__} must inherit from AbstractPaymentService.")

    def add(self, *service_classes: type) -> PaymentConfigBuilder:
        for service_class in service_classes:
            self.validate_service_class(service_class)
        self.service_classes = _merge_unique_classes(self.service_classes, service_classes)
        return self

    def get_registered_systems(self) -> set[str]:
        return {str(service_class.payment_system) for service_class in self.service_classes}


class CommerceModule:
    """РЇРІРЅР°СЏ С‚РѕС‡РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ `commerce` Рє РїСЂРѕРµРєС‚Сѓ."""

    def __init__(
            self,
            *,
            config_class: type[BaseConfig] = BaseConfig,
            product_orders: ProductOrderConfigBuilder | None = None,
            order_runtime: OrderRuntimeConfigBuilder | None = None,
            payments: PaymentConfigBuilder | None = None,
    ) -> None:
        self.config_class = config_class
        self.product_orders = product_orders or ProductOrderConfigBuilder()
        self.order_runtime = order_runtime or OrderRuntimeConfigBuilder()
        self.payments = payments or PaymentConfigBuilder()
        self.config_class.validate()
        self.validate_payment_systems()

    def validate_payment_systems(self) -> None:
        registered_systems = self.payments.get_registered_systems()
        payment_systems_map = self.config_class.get_payment_systems_map()
        if not registered_systems:
            raise TypeError(
                "CommerceModule requires at least one registered payment service in PaymentConfigBuilder.",
            )
        for currency, payment_systems in payment_systems_map.items():
            for payment_system in payment_systems:
                if payment_system not in registered_systems:
                    raise TypeError(
                        f"{self.config_class.__name__}.PAYMENT_SYSTEMS[{currency}] contains "
                        f"'{payment_system}', but this payment service is not registered in CommerceModule.",
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
        payments=PaymentConfigBuilder(HandMadePaymentService, BalancePaymentService),
    )


