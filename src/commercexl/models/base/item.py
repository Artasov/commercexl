from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase
from commercexl.order import OrderItemState


class OrderItemORM(CommerceBase):
    """Одна позиция внутри коммерческого заказа."""

    __tablename__ = "commerce_orderitem"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'ready', 'executed', 'cancelled', 'refunded')",
            name="commerce_orderitem_state",
        ),
        CheckConstraint("amount >= 0", name="commerce_orderitem_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("commerce_order.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=OrderItemState.CREATED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def item_state(self) -> OrderItemState:
        """Возвращает persisted state как строгий enum."""
        return OrderItemState(self.state)
