from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer
from sqlalchemy import Numeric


class Money:
    """Определяет точный контракт коммерческой суммы CommerceXL."""

    precision = 20
    scale = 6
    currency_code_length = 12

    @classmethod
    def parse(cls, value: Any) -> Decimal:
        """Принимает Decimal внутри Python и decimal-string на внешней границе."""
        if isinstance(value, bool) or not isinstance(value, (Decimal, str)):
            raise ValueError("Money amount must be a decimal string.")
        try:
            amount = value if isinstance(value, Decimal) else Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Money amount is invalid.") from exc
        if not amount.is_finite():
            raise ValueError("Money amount must be finite.")
        if amount.as_tuple().exponent < -cls.scale:
            raise ValueError(f"Money amount supports at most {cls.scale} decimal places.")
        if amount and amount.adjusted() >= cls.precision - cls.scale:
            raise ValueError("Money amount exceeds the supported precision.")
        return amount

    @staticmethod
    def serialize(value: Decimal) -> str:
        """Возвращает каноническую decimal-string без scientific notation."""
        if value == 0:
            return "0"
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    @classmethod
    def sql_type(cls) -> Numeric:
        """Создаёт SQLAlchemy-тип для коммерческой суммы."""
        return Numeric(cls.precision, cls.scale)


MoneyAmount = Annotated[
    Decimal,
    BeforeValidator(Money.parse),
    PlainSerializer(Money.serialize, return_type=str, when_used="json"),
]
