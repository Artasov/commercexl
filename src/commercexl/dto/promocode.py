from pydantic import BaseModel


class PromocodeDiscountDTO(BaseModel):
    id: int
    product: int
    currency: str
    amount: float
    max_usage: int | None = None
    max_usage_per_user: int | None = None
    interval_days: int | None = None


class PromocodeDTO(BaseModel):
    id: int
    name: str
    code: str
    description: str | None = None
    discount_type: str
    start_date: str
    end_date: str | None = None
    discounts: list[PromocodeDiscountDTO]


