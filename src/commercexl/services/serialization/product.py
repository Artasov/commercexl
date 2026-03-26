from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import ProductDTO, ProductPriceDTO
from commercexl.models.base import ProductORM, ProductPriceORM
from commercexl.models.products.balance import BalanceProductORM
from commercexl.services.base_runtime import BaseRuntime
from commercexl.utils import build_media_url


class ProductSerializer(BaseRuntime):
    """РЎРµСЂРёР°Р»РёР·Р°С†РёСЏ РїСѓР±Р»РёС‡РЅС‹С… РґР°РЅРЅС‹С… РїСЂРѕРґСѓРєС‚Р°."""

    async def get_latest_balance_product(self, session: AsyncSession) -> ProductDTO | None:
        query = (
            select(ProductORM)
            .join(BalanceProductORM, BalanceProductORM.product_ptr_id == ProductORM.id)
            .order_by(ProductORM.id.desc())
            .limit(1)
        )
        product = (await session.execute(query)).scalar_one_or_none()
        if product is None:
            return None
        return await self.serialize_product(session, product)

    async def list_products(self, session: AsyncSession) -> list[ProductDTO]:
        query = select(ProductORM).where(ProductORM.is_available.is_(True)).order_by(ProductORM.id.asc())
        products = list((await session.execute(query)).scalars())
        return [await self.serialize_product(session, product) for product in products]

    @staticmethod
    async def serialize_product(session: AsyncSession, product: ProductORM) -> ProductDTO:
        prices_query = select(ProductPriceORM).where(ProductPriceORM.product_id == product.id).order_by(
            ProductPriceORM.id.asc(),
        )
        prices = list((await session.execute(prices_query)).scalars())
        return ProductDTO(
            id=product.id,
            name=product.name,
            pic=build_media_url(None, product.pic),
            description=product.description,
            short_description=product.short_description,
            is_available=product.is_available,
            is_installment_available=product.is_installment_available,
            kind=product.kind,
            prices=[
                ProductPriceDTO(
                    id=price.id,
                    product=product.id,
                    currency=price.currency,
                    amount=float(price.amount),
                    exponent=float(price.exponent) if price.exponent is not None else None,
                    offset=float(price.offset) if price.offset is not None else None,
                )
                for price in prices
            ],
        )


