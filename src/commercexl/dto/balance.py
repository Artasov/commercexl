from pydantic import BaseModel


class UserBalanceDTO(BaseModel):
    balance: float


