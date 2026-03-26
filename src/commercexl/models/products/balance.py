from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class BalanceProductORM(CommerceBase):
    """Р”РѕС‡РµСЂРЅСЏСЏ Р·Р°РїРёСЃСЊ РІСЃС‚СЂРѕРµРЅРЅРѕРіРѕ РїСЂРѕРґСѓРєС‚Р° РїРѕРїРѕР»РЅРµРЅРёСЏ Р±Р°Р»Р°РЅСЃР°."""

    __tablename__ = "commerce_balance_product"

    product_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_product.id"), primary_key=True)


class BalanceOrderItemORM(CommerceBase):
    """Р”РѕС‡РµСЂРЅСЏСЏ Р·Р°РїРёСЃСЊ РїРѕР·РёС†РёРё Р·Р°РєР°Р·Р° РїРѕРїРѕР»РЅРµРЅРёСЏ Р±Р°Р»Р°РЅСЃР°."""

    __tablename__ = "commerce_balance_order_item"

    order_item_id: Mapped[int] = mapped_column(ForeignKey("commerce_orderitem.id"), primary_key=True)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    credited_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))


