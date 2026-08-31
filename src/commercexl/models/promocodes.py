from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase

commerce_promocode_discounts = Table(
    "commerce_promocode_discounts",
    CommerceBase.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("promocode_id", ForeignKey("commerce_promocode.id"), nullable=False),
    Column("promocodeproductdiscount_id", ForeignKey("commerce_promocodeproductdiscount.id"), nullable=False),
    UniqueConstraint(
        "promocode_id",
        "promocodeproductdiscount_id",
        name="uq_commerce_promocode_discounts_pair",
    ),
)

commerce_promocodeproductdiscount_specific_users = Table(
    "commerce_promocodeproductdiscount_specific_users",
    CommerceBase.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("promocodeproductdiscount_id", ForeignKey("commerce_promocodeproductdiscount.id"), nullable=False),
    Column("user_id", BigInteger, nullable=False),
    UniqueConstraint(
        "promocodeproductdiscount_id",
        "user_id",
        name="uq_commerce_promocodeproductdiscount_user",
    ),
)


class PromocodeProductDiscountORM(CommerceBase):
    """Денежная или процентная скидка продукта в одной валюте."""

    __tablename__ = "commerce_promocodeproductdiscount"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="commerce_promocode_discount_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    currency: Mapped[str] = mapped_column(String(Money.currency_code_length), nullable=False)
    max_usage: Mapped[int | None] = mapped_column(SmallInteger)
    max_usage_per_user: Mapped[int | None] = mapped_column(SmallInteger)
    interval_days: Mapped[int | None] = mapped_column(SmallInteger)


class PromocodeORM(CommerceBase):
    """Промокод с периодом действия и набором скидок."""

    __tablename__ = "commerce_promocode"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PromocodeUsageORM(CommerceBase):
    """Фиксирует одно использование промокода пользователем."""

    __tablename__ = "commerce_promocodeusage"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("commerce_promocode.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
