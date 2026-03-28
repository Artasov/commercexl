from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class Currency(StrEnum):
    """Встроенные коды валют как удобные константы. Проект может использовать и обычные строки."""

    USD = "USD"
    RUB = "RUB"
    EUR = "EUR"
    SOL = "SOL"


class PaymentORM(CommerceBase):
    """Базовая запись оплаты без привязки к конкретной платёжной системе."""

    __tablename__ = "commerce_payment"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_url: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
