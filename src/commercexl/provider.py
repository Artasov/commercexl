from __future__ import annotations

from collections.abc import Callable

from commercexl.module import CommerceModule, get_default_commerce_module

CommerceProvider = Callable[[], CommerceModule]

_commerce_provider: CommerceProvider | None = None


def set_commerce_provider(provider: CommerceProvider) -> None:
    """Регистрирует project-level provider для core `commerce`."""
    global _commerce_provider
    _commerce_provider = provider


def get_commerce() -> CommerceModule:
    """Возвращает project-level `CommerceModule` или builtin-конфиг по умолчанию."""
    if _commerce_provider is not None:
        return _commerce_provider()
    return get_default_commerce_module()


__all__ = ("get_commerce", "set_commerce_provider")


