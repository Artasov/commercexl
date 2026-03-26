from pydantic import BaseModel


class CreateOrderProductRequest(BaseModel):
    product: int | str
    requested_amount: float | None = None
    license_hours: int | None = None


class CreateOrderRequest(BaseModel):
    product: int | str | None = None
    products: list[CreateOrderProductRequest] | None = None
    currency: str
    payment_system: str
    requested_amount: float | None = None
    license_hours: int | None = None
    promocode: int | str | None = None
    email: str | None = None


