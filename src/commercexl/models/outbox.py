from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class PaymentOutboxEventORM(CommerceBase):
    """Событие платежа, записанное атомарно с изменением финансового состояния."""

    __tablename__ = "commerce_payment_outbox"
    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "revision",
            "event_type",
            name="uq_commerce_payment_outbox_payment_revision_type",
        ),
        CheckConstraint("revision > 0", name="commerce_payment_outbox_revision_positive"),
        CheckConstraint(
            "delivery_attempts >= 0",
            name="commerce_payment_outbox_delivery_attempts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), nullable=False, index=True)
    payment_public_id: Mapped[UUID] = mapped_column(nullable=False)
    order_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(100))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000))
