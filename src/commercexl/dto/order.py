from pydantic import BaseModel, ConfigDict

from commercexl.dto.payment import PaymentDTO
from commercexl.dto.product import ProductDTO
from commercexl.dto.promocode import PromocodeDTO


class OrderDTO(BaseModel):
    """Единая DTO заказа для API с общими полями и optional-полями конкретного продукта."""

    id: str
    amount: float | None = None
    payment: PaymentDTO | None = None
    currency: str
    payment_system: str
    promocode: PromocodeDTO | None = None
    created_at: str
    updated_at: str
    state: str
    is_inited: bool
    is_paid: bool
    is_executed: bool
    is_cancelled: bool
    is_refunded: bool
    product: ProductDTO | None = None
    requested_amount: float | None = None
    credited_amount: float | None = None
    key: str | None = None
    license_hours: int | None = None
    items: list["OrderItemDTO"] | None = None


class OrderItemDTO(BaseModel):
    """Одна позиция внутри общего заказа с несколькими продуктами."""

    id: str
    amount: float | None = None
    currency: str
    state: str
    is_inited: bool
    is_paid: bool
    is_executed: bool
    is_cancelled: bool
    is_refunded: bool
    product: ProductDTO | None = None
    requested_amount: float | None = None
    credited_amount: float | None = None
    key: str | None = None
    license_hours: int | None = None


class CreateOrderIdOnlyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str


class CreateOrderDTO(BaseModel):
    id: str
    payment_url: str | None = None


OrderDTO.model_rebuild()


