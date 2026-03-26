from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Table, \
    UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
    __tablename__ = "commerce_promocodeproductdiscount"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    max_usage: Mapped[int | None] = mapped_column(SmallInteger)
    max_usage_per_user: Mapped[int | None] = mapped_column(SmallInteger)
    interval_days: Mapped[int | None] = mapped_column(SmallInteger)
    product_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), nullable=False)


class PromocodeORM(CommerceBase):
    __tablename__ = "commerce_promocode"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromocodeUsageORM(CommerceBase):
    __tablename__ = "commerce_promocodeusage"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("commerce_promocode.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)


