from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class OrderItemORM(CommerceBase):
    """Одна позиция внутри заказа."""

    __tablename__ = "commerce_orderitem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("commerce_order.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_inited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def state(self) -> str:
        if self.is_refunded: return "refunded"
        if self.is_cancelled: return "cancelled"
        if self.is_executed: return "executed"
        if self.is_paid: return "paid"
        if self.is_inited: return "inited"
        return "created"

