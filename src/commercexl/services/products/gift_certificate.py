from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.models import OrderItemORM, OrderORM, ProductORM
from commercexl.models.products.gift_certificate import (
    GiftCertificateORM,
    GiftCertificateOrderItemORM,
    GiftCertificateUsageORM,
)
from commercexl.services.order.base import AbstractOrderItemService
from commercexl.services.products.base import AbstractProductService


class GiftCertificateOrderItemService(AbstractOrderItemService):
    """Order-item сервис подарочного сертификата."""

    async def create_item_record(
            self,
            payload: dict[str, object],
            amount: Decimal,
    ) -> GiftCertificateOrderItemORM:
        _ = payload
        _ = amount
        self.item_record = GiftCertificateOrderItemORM(order_item_id=self.order_item.id, key=uuid4())
        return self.item_record


class GiftCertificateProductService(AbstractProductService[GiftCertificateOrderItemORM]):
    """
    Встроенный продукт подарочного сертификата.

    Сертификат не выдаёт целевой продукт сразу после оплаты.
    После покупки он создаёт ключ, а сама выдача происходит при активации.
    """

    kind = "gift_certificate"
    product_kinds = ("giftcertificate", "gift_certificate")
    item_kinds = ("giftcertificateitem", "gift_certificate")
    product_model = GiftCertificateORM
    item_model = GiftCertificateOrderItemORM
    default_order_item_service_class = GiftCertificateOrderItemService


class GiftCertificate:
    """
    Каталог и активация подарочных сертификатов.

    Сервис нужен уже после покупки: посмотреть продукт сертификата и активировать ключ.
    """

    def __init__(self, commerce_module) -> None:
        self.commerce_module = commerce_module
        self.base_runtime = commerce_module.create_base_runtime()
        self.order_runtime = commerce_module.create_order_runtime()
        self.product_serializer = commerce_module.create_product_serializer()

    async def serialize(self, session: AsyncSession, gift_certificate: GiftCertificateORM) -> dict:
        product: ProductORM | None = await session.get(ProductORM, gift_certificate.product_ptr_id)
        if product is None:
            raise self.base_runtime.get_not_found("Gift certificate product not found.")

        target_product: ProductORM | None = await session.get(ProductORM, gift_certificate.product_id)
        if target_product is None:
            raise self.base_runtime.get_not_found("Gift certificate target product not found.")

        payload = (await self.product_serializer.serialize_product(session, product)).model_dump()
        payload["product"] = (await self.product_serializer.serialize_product(session, target_product)).model_dump()
        return payload

    async def list(self, session: AsyncSession) -> list[dict]:
        query = select(GiftCertificateORM).order_by(GiftCertificateORM.product_ptr_id.asc())
        items = list((await session.execute(query)).scalars())
        return [await self.serialize(session, item) for item in items]

    async def get(self, session: AsyncSession, product_id: int) -> dict:
        gift_certificate: GiftCertificateORM | None = await session.get(GiftCertificateORM, product_id)
        if gift_certificate is None:
            raise self.base_runtime.get_not_found("Gift certificate not found.")
        return await self.serialize(session, gift_certificate)

    async def activate(self, session: AsyncSession, user_id: int, key: UUID) -> None:
        """
        Активирует ключ и применяет эффект целевого продукта.

        Новый заказ здесь не создаётся. Мы используем уже оплаченный `OrderItemORM`
        сертификата и вызываем `apply_product_effect(...)` для целевого продукта.
        """
        query = select(GiftCertificateOrderItemORM).where(GiftCertificateOrderItemORM.key == key).limit(1)
        item_record = (await session.execute(query)).scalar_one_or_none()
        if item_record is None:
            raise self.base_runtime.get_not_found("gift_certificate_key_not_found")

        usage_query = select(GiftCertificateUsageORM).where(GiftCertificateUsageORM.order_item_id == item_record.order_item_id)
        existing_usage = (await session.execute(usage_query)).scalar_one_or_none()
        if existing_usage is not None:
            raise self.base_runtime.get_bad_request("Gift certificate already activated.")

        order_item = await session.get(OrderItemORM, item_record.order_item_id)
        if order_item is None:
            raise self.base_runtime.get_not_found("Order item not found.")

        order = await session.get(OrderORM, order_item.order_id)
        if order is None:
            raise self.base_runtime.get_not_found("Order not found.")

        target_product: GiftCertificateORM | None = await session.get(GiftCertificateORM, order_item.product_id)
        if target_product is None:
            raise self.base_runtime.get_not_found("Gift certificate product not found.")

        await self.order_runtime.apply_product_effect(
            session,
            user_id=user_id,
            product_id=target_product.product_id,
            currency=str(order.currency),
            amount=Decimal(str(order_item.amount or 0)),
            license_hours=None,
        )
        session.add(
            GiftCertificateUsageORM(
                created_at=datetime.now(UTC),
                order_item_id=item_record.order_item_id,
                user_id=user_id,
            ),
        )


__all__ = (
    "GiftCertificate",
    "GiftCertificateORM",
    "GiftCertificateOrderItemORM",
    "GiftCertificateOrderItemService",
    "GiftCertificateProductService",
    "GiftCertificateUsageORM",
)
