from __future__ import annotations

from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO
from commercexl.services.base_runtime import BaseRuntime


def get_base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


async def load_order_payload(session: AsyncSession, order_id: str | UUID, runtime: BaseRuntime) -> OrderDTO:
    """Всегда возвращает актуальную DTO заказа после изменения в БД."""
    order = await runtime.refresh_order(session, order_id)
    return await runtime.create_order_serializer().serialize_order(session, order)


