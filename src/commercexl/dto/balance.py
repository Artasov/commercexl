from pydantic import BaseModel, ConfigDict

from commercexl.money import MoneyAmount


class UserBalanceDTO(BaseModel):
    """Точный баланс пользователя в виде Decimal/string контракта."""

    model_config = ConfigDict(extra="forbid")

    balance: MoneyAmount
