from __future__ import annotations

from collections.abc import Callable

from commercexl.module import CommerceModule, get_default_commerce_module

CommerceProvider = Callable[[], CommerceModule]

_commerce_provider: CommerceProvider | None = None


def set_commerce_provider(provider: CommerceProvider) -> None:
    """Р РµРіРёСЃС‚СЂРёСЂСѓРµС‚ project-level provider РґР»СЏ core `commerce`."""
    global _commerce_provider
    _commerce_provider = provider


def get_commerce() -> CommerceModule:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ project-level `CommerceModule` РёР»Рё builtin-РєРѕРЅС„РёРі РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ."""
    if _commerce_provider is not None:
        return _commerce_provider()
    return get_default_commerce_module()


__all__ = ("get_commerce", "set_commerce_provider")


