from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.money import Money
from commercexl.models.orm_base import CommerceBase


class UserCreditsBalanceORM(CommerceBase):
    """Баланс внутренних кредитов пользователя."""

    __tablename__ = "commerce_user_credits_balance"
    __table_args__ = (
        UniqueConstraint("user_id", name="commerce_user_credits_balance_user_id_key"),
        CheckConstraint("amount >= 0", name="commerce_user_credits_balance_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money.sql_type(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
