from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO
from commercexl.models import OrderORM


class OrderAccessAction(StrEnum):
    """Действия над заказом, решение по которым принадлежит host-приложению."""

    VIEW = "view"
    CREATE_PAYMENT = "create_payment"
    CANCEL = "cancel"
    MANAGE = "manage"


class AbstractOrderAccessPolicy(ABC):
    """Порт ownership и permission-проверок без зависимости от auth-пакета."""

    @abstractmethod
    async def is_allowed(
            self,
            session: AsyncSession,
            actor: CommerceUserActorDTO,
            order: OrderORM,
            action: OrderAccessAction,
    ) -> bool:
        """Возвращает решение host-политики для конкретного заказа."""
        raise NotImplementedError


class OwnerOrderAccessPolicy(AbstractOrderAccessPolicy):
    """Разрешает владельцу обычные действия, а commerce manager — любые."""

    async def is_allowed(
            self,
            session: AsyncSession,
            actor: CommerceUserActorDTO,
            order: OrderORM,
            action: OrderAccessAction,
    ) -> bool:
        _ = session
        if actor.has_permission("commerce.manage"):
            return True
        if action == OrderAccessAction.MANAGE:
            return False
        return order.user_id == actor.id
