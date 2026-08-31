from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class PaymentEvidenceORM(CommerceBase):
    """Глобально связывает provider evidence только с одной payment attempt."""

    __tablename__ = "commerce_payment_evidence"
    __table_args__ = (
        UniqueConstraint(
            "payment_system",
            "evidence_key",
            name="uq_commerce_payment_evidence_system_key",
        ),
        CheckConstraint(
            "state IN ('requires_action', 'processing', 'observed', 'confirmed', 'paid', 'expired', "
            "'cancelled', 'failed', 'review', 'refund_pending', 'refunded')",
            name="commerce_payment_evidence_state",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    payment_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), nullable=False, index=True)
    payment_system: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
