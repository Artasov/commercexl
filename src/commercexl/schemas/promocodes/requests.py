from pydantic import BaseModel


class PromocodeCheckRequest(BaseModel):
    promocode: str
    product: int
    currency: str


