from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from commercexl.dto.payment import PaymentDTO
from commercexl.dto.product import ProductDTO
from commercexl.dto.promocode import PromocodeDTO
from commercexl.money import MoneyAmount
from commercexl.order import OrderItemState, OrderState


class OrderItemDTO(BaseModel):
    """Одна позиция заказа без дублирования флагов состояния."""

    model_config = ConfigDict(extra="forbid")

    id: int
    amount: MoneyAmount
    state: OrderItemState
    product: ProductDTO | None = None
    requested_amount: MoneyAmount | None = None
    credited_amount: MoneyAmount | None = None
    key: str | None = None
    license_hours: int | None = None


class OrderDTO(BaseModel):
    """Provider-neutral заказ с текущей последней попыткой оплаты."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    amount: MoneyAmount
    currency: str
    state: OrderState
    payment: PaymentDTO | None = None
    promocode: PromocodeDTO | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemDTO]


class CreateOrderDTO(BaseModel):
    """Результат первой фазы checkout без неявной payment URL semantics."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    amount: MoneyAmount
    currency: str
    state: OrderState
