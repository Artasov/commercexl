from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class OrderORM(CommerceBase):
    """Базовая запись заказа с общими полями любого продукта."""

    __tablename__ = "commerce_order"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_system: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("commerce_payment.id"))
    is_inited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promocode_id: Mapped[int | None] = mapped_column(ForeignKey("commerce_promocode.id"))
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def state(self) -> str:
        """Общее состояние заказа на уровне core checkout flow."""
        if self.is_refunded: return "refunded"
        if self.is_cancelled: return "cancelled"
        if self.is_executed: return "executed"
        if self.is_paid: return "paid"
        if self.is_inited: return "inited"
        return "created"

