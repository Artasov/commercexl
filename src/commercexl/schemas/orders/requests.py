from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commercexl.money import MoneyAmount


class CreateOrderProductRequest(BaseModel):
    """Одна product selection в server-priced заказе."""

    model_config = ConfigDict(extra="forbid")

    product: int | str
    requested_amount: MoneyAmount | None = None
    license_hours: int | None = None


class CreateOrderRequest(BaseModel):
    """Создаёт только заказ; payment option выбирается отдельной операцией."""

    model_config = ConfigDict(extra="forbid")

    product: int | str | None = None
    products: list[CreateOrderProductRequest] | None = Field(default=None, min_length=1)
    currency: str
    requested_amount: MoneyAmount | None = None
    license_hours: int | None = None
    promocode: int | str | None = None
    email: str | None = None

    @model_validator(mode="after")
    def validate_product_selection(self) -> CreateOrderRequest:
        if (self.product is None) == (self.products is None):
            raise ValueError("Exactly one of product or products is required.")
        if self.products is not None and (
                self.requested_amount is not None
                or self.license_hours is not None
        ):
            raise ValueError("Product-specific fields must be set inside each products item.")
        return self
