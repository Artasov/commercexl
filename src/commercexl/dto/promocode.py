from pydantic import BaseModel, ConfigDict

from commercexl.money import MoneyAmount


class PromocodeDiscountDTO(BaseModel):
    """Точное значение скидки промокода."""

    model_config = ConfigDict(extra="forbid")

    id: int
    product: int
    currency: str
    amount: MoneyAmount
    max_usage: int | None = None
    max_usage_per_user: int | None = None
    interval_days: int | None = None


class PromocodeDTO(BaseModel):
    """Публичный промокод с применимыми скидками."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    code: str
    description: str | None = None
    discount_type: str
    start_date: str
    end_date: str | None = None
    discounts: list[PromocodeDiscountDTO]
