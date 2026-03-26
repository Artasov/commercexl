from pydantic import BaseModel


class InitPaymentRequest(BaseModel):
    payment_system: str
    currency: str
    amount: float = 0


