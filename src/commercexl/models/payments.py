from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class BalancePaymentORM(CommerceBase):
    """Дочерняя запись оплаты внутренним балансом."""

    __tablename__ = "commerce_balance_payment"

    payment_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), primary_key=True)


class HandMadePaymentORM(CommerceBase):
    """Дочерняя запись ручной оплаты."""

    __tablename__ = "commerce_handmade_payment"

    payment_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), primary_key=True)
