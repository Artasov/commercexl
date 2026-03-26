from __future__ import annotations

from typing import TYPE_CHECKING

from commercexl.module import ProductOrderConfig
from commercexl.services.products.base import AbstractProductService

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime


class Registry:
    """
    РҐСЂР°РЅРёС‚ product-service РєР»Р°СЃСЃС‹ Рё Р±С‹СЃС‚СЂРѕ РЅР°С…РѕРґРёС‚ РЅСѓР¶РЅС‹Р№ РїРѕ С‚РёРїСѓ РїСЂРѕРґСѓРєС‚Р° РёР»Рё РїРѕР·РёС†РёРё Р·Р°РєР°Р·Р°.

    Р—РґРµСЃСЊ product-service СЌС‚Рѕ РєР»Р°СЃСЃ РїСЂРѕРґСѓРєС‚Р° РІРЅСѓС‚СЂРё `commerce`: РѕРЅ Р·РЅР°РµС‚ СЃРІРѕР№ `kind`,
    РєР°РєРёРµ `ProductORM.kind` РµРјСѓ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‚ Рё РєР°РєР°СЏ item-РјРѕРґРµР»СЊ РѕС‚РЅРѕСЃРёС‚СЃСЏ Рє РµРіРѕ РїРѕР·РёС†РёРё Р·Р°РєР°Р·Р°.
    """

    def __init__(
            self,
            commerce: BaseRuntime,
            configs: tuple[ProductOrderConfig, ...],
    ) -> None:
        self._handlers_by_kind: dict[str, AbstractProductService] = {}
        self._handlers_by_product_kind: dict[str, AbstractProductService] = {}
        self._handlers_by_item_kind: dict[str, AbstractProductService] = {}
        self._configs_by_kind: dict[str, ProductOrderConfig] = {}

        handlers: list[AbstractProductService] = []
        for config in configs:
            for product_service_class in config.product_service_classes:
                handler = product_service_class(
                    commerce,
                    order_item_service_class=config.order_item_service_class,
                )
                handlers.append(handler)

                normalized_kind = self.normalize_kind(handler.kind)
                if normalized_kind:
                    self._handlers_by_kind.setdefault(normalized_kind, handler)
                    self._configs_by_kind.setdefault(normalized_kind, config)

                for product_kind in handler.product_kinds:
                    normalized_product_kind = self.normalize_kind(product_kind)
                    if normalized_product_kind:
                        self._handlers_by_product_kind.setdefault(normalized_product_kind, handler)

                for item_kind in handler.item_kinds:
                    normalized_item_kind = self.normalize_kind(item_kind)
                    if normalized_item_kind:
                        self._handlers_by_item_kind.setdefault(normalized_item_kind, handler)

        self.handlers = tuple(handlers)

    @staticmethod
    def normalize_kind(kind: str | None) -> str:
        return str(kind or "").strip().lower()

    def get_handler_by_kind(self, kind: str | None) -> AbstractProductService | None:
        return self._handlers_by_kind.get(self.normalize_kind(kind))

    def get_handler_by_product_kind(self, kind: str | None) -> AbstractProductService | None:
        return self._handlers_by_product_kind.get(self.normalize_kind(kind))

    def get_handler_by_item_kind(self, kind: str | None) -> AbstractProductService | None:
        return self._handlers_by_item_kind.get(self.normalize_kind(kind))

    def get_config_by_kind(self, kind: str | None) -> ProductOrderConfig | None:
        return self._configs_by_kind.get(self.normalize_kind(kind))


