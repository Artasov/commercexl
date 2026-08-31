from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from commercexl.money import MoneyAmount
from commercexl.payment import CheckoutAction, PaymentOptionDTO, PaymentState


class PaymentDTO(BaseModel):
    """Публичное состояние канонической попытки оплаты."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    order_id: UUID
    attempt_no: int
    amount: MoneyAmount
    currency: str
    payment_system: str
    provider_kind: str
    payment_option_id: str
    state: PaymentState
    action: CheckoutAction | None = None
    reason_code: str | None = None
    revision: int
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentOptionsDTO(BaseModel):
    """Доступные server-side payment options конкретного заказа."""

    model_config = ConfigDict(extra="forbid")

    options: list[PaymentOptionDTO]
