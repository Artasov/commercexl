from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class UserBalanceORM(CommerceBase):
    """Р‘Р°Р»Р°РЅСЃ РІРЅСѓС‚СЂРµРЅРЅРёС… РєСЂРµРґРёС‚РѕРІ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""

    __tablename__ = "commerce_user_balance"
    __table_args__ = (UniqueConstraint("user_id", name="commerce_user_balance_user_id_key"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)


