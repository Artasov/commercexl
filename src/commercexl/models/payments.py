from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class BalancePaymentORM(CommerceBase):
    """Р”РѕС‡РµСЂРЅСЏСЏ Р·Р°РїРёСЃСЊ РѕРїР»Р°С‚С‹ РІРЅСѓС‚СЂРµРЅРЅРёРј Р±Р°Р»Р°РЅСЃРѕРј."""

    __tablename__ = "commerce_balance_payment"

    payment_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), primary_key=True)


class HandMadePaymentORM(CommerceBase):
    """Р”РѕС‡РµСЂРЅСЏСЏ Р·Р°РїРёСЃСЊ СЂСѓС‡РЅРѕР№ РѕРїР»Р°С‚С‹."""

    __tablename__ = "commerce_handmade_payment"

    payment_ptr_id: Mapped[int] = mapped_column(ForeignKey("commerce_payment.id"), primary_key=True)


