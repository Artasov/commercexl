from pydantic import BaseModel, ConfigDict

from commercexl.money import MoneyAmount


class ProductPriceDTO(BaseModel):
    """Точная цена продукта без float round-trip."""

    model_config = ConfigDict(extra="forbid")

    id: int
    product: int
    currency: str
    amount: MoneyAmount
    exponent: MoneyAmount | None = None
    offset: MoneyAmount | None = None


class ProductDTO(BaseModel):
    """Публичное описание продукта и его server-side prices."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    pic: str | None = None
    description: str | None = None
    short_description: str | None = None
    is_available: bool
    is_installment_available: bool
    kind: str
    prices: list[ProductPriceDTO]
