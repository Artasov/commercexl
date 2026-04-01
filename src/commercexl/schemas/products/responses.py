from pydantic import BaseModel

from commercexl.dto import ProductDTO, UserBalanceDTO


class GiftCertificateResponse(ProductDTO):
    product: ProductDTO


class GiftCertificateActivateResponse(BaseModel):
    detail: str


ProductResponse = ProductDTO
UserBalanceResponse = UserBalanceDTO
