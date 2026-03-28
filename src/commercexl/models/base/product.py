from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class ProductORM(CommerceBase):
    """Базовая запись продукта в каталоге commerce."""

    __tablename__ = "commerce_product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pic: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_installment_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductPriceORM(CommerceBase):
    """Цена продукта в конкретной валюте."""

    __tablename__ = "commerce_product_price"
    __table_args__ = (
        UniqueConstraint("product_id", "currency", name="commerce_product_price_product_id_currency_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    offset: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

