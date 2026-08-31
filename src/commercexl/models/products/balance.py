from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase


class BalanceProductORM(CommerceBase):
    """Дочерняя запись встроенного продукта пополнения баланса."""

    __tablename__ = "commerce_balance_product"

    product_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), primary_key=True)


class BalanceOrderItemORM(CommerceBase):
    """Дочерняя запись позиции заказа пополнения баланса."""

    __tablename__ = "commerce_balance_order_item"
    __table_args__ = (
        CheckConstraint("requested_amount >= 0", name="commerce_balance_item_requested_nonnegative"),
        CheckConstraint(
            "credited_amount IS NULL OR credited_amount >= 0",
            name="commerce_balance_item_credited_nonnegative",
        ),
    )

    order_item_id: Mapped[int] = mapped_column(ForeignKey("commerce_orderitem.id"), primary_key=True)
    requested_amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    credited_amount: Mapped[Decimal | None] = mapped_column(Money.sql_type())
