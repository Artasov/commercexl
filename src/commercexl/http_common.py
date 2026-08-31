from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO
from commercexl.services.base_runtime import BaseRuntime


async def load_order_payload(
        session: AsyncSession,
        order_id: str | UUID,
        runtime: BaseRuntime,
) -> OrderDTO:
    """Возвращает актуальную DTO заказа после mutation."""
    order = await runtime.refresh_order(session, order_id)
    return await runtime.create_order_serializer().serialize_order(session, order)
