from pydantic import BaseModel


class ProductPriceDTO(BaseModel):
    id: int
    product: int
    currency: str
    amount: float
    exponent: float | None = None
    offset: float | None = None


class ProductDTO(BaseModel):
    id: int
    name: str
    pic: str | None = None
    description: str | None = None
    short_description: str | None = None
    is_available: bool
    is_installment_available: bool
    kind: str
    prices: list[ProductPriceDTO]


