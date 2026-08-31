from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase
from commercexl.order import OrderState


class OrderORM(CommerceBase):
    """Коммерческий заказ, создаваемый до выбора способа оплаты."""

    __tablename__ = "commerce_order"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_commerce_order_user_id_idempotency_key",
        ),
        CheckConstraint(
            "state IN ('created', 'ready_for_payment', 'executed', 'cancelled', 'refunded')",
            name="commerce_order_state",
        ),
        CheckConstraint("amount >= 0", name="commerce_order_amount_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    currency: Mapped[str] = mapped_column(String(Money.currency_code_length), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=OrderState.CREATED.value, index=True)
    promocode_id: Mapped[int | None] = mapped_column(ForeignKey("commerce_promocode.id"))
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def order_state(self) -> OrderState:
        """Возвращает persisted state как строгий enum."""
        return OrderState(self.state)
