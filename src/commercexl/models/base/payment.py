from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class Currency(StrEnum):
    """Р’СЃС‚СЂРѕРµРЅРЅС‹Рµ РєРѕРґС‹ РІР°Р»СЋС‚ РєР°Рє СѓРґРѕР±РЅС‹Рµ РєРѕРЅСЃС‚Р°РЅС‚С‹. РџСЂРѕРµРєС‚ РјРѕР¶РµС‚ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ Рё РѕР±С‹С‡РЅС‹Рµ СЃС‚СЂРѕРєРё."""

    USD = "USD"
    RUB = "RUB"
    EUR = "EUR"
    SOL = "SOL"


class PaymentORM(CommerceBase):
    """Р‘Р°Р·РѕРІР°СЏ Р·Р°РїРёСЃСЊ РѕРїР»Р°С‚С‹ Р±РµР· РїСЂРёРІСЏР·РєРё Рє РєРѕРЅРєСЂРµС‚РЅРѕР№ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃРёСЃС‚РµРјРµ."""

    __tablename__ = "commerce_payment"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_url: Mapped[str | None] = mapped_column(String(500))
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))


