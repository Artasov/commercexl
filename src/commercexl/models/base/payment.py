from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase
from commercexl.payment import PaymentState


class Currency(StrEnum):
    """Встроенные коммерческие currency codes без blockchain asset identity."""

    USD = "USD"
    RUB = "RUB"
    EUR = "EUR"
    SOL = "SOL"


class PaymentORM(CommerceBase):
    """Каноническая попытка оплаты и extension root провайдерских таблиц."""

    __tablename__ = "commerce_payment"
    __table_args__ = (
        UniqueConstraint("order_id", "attempt_no", name="uq_commerce_payment_order_id_attempt_no"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_commerce_payment_user_id_idempotency_key"),
        UniqueConstraint("order_id", "active_slot", name="uq_commerce_payment_order_id_active_slot"),
        CheckConstraint("attempt_no > 0", name="commerce_payment_attempt_no_positive"),
        CheckConstraint("amount >= 0", name="commerce_payment_amount_nonnegative"),
        CheckConstraint("revision >= 0", name="commerce_payment_revision_nonnegative"),
        CheckConstraint("active_slot IS NULL OR active_slot = 1", name="commerce_payment_active_slot_value"),
        CheckConstraint(
            "(active_slot = 1 AND state IN "
            "('created', 'requires_action', 'processing', 'observed', 'confirmed', 'paid', 'review', "
            "'refund_pending')) "
            "OR (active_slot IS NULL AND state IN "
            "('expired', 'cancelled', 'failed', 'refunded'))",
            name="commerce_payment_state_active_slot",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    public_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("commerce_order.id"), nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    active_slot: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    currency: Mapped[str] = mapped_column(String(Money.currency_code_length), nullable=False)
    payment_system: Mapped[str] = mapped_column(String(50), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payment_option_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=PaymentState.CREATED.value, index=True)
    action_kind: Mapped[str | None] = mapped_column(String(50))
    reason_code: Mapped[str | None] = mapped_column(String(100))
    verification_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def payment_state(self) -> PaymentState:
        """Возвращает state как строгий enum."""
        return PaymentState(self.state)

    @property
    def is_terminal(self) -> bool:
        """Показывает, завершена ли попытка оплаты."""
        return self.payment_state.is_terminal
