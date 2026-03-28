from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.base import OrderItemORM, ProductORM
from commercexl.models.orm_base import CommerceBase


class GiftCertificateORM(CommerceBase):
    """
    Продукт подарочного сертификата.

    `product_ptr_id` это сам продукт сертификата в каталоге.
    `product_id` это целевой продукт, эффект которого будет выдан по ключу.
    """

    __tablename__ = "commerce_gift_certificate_product"

    product_ptr_id: Mapped[int] = mapped_column(ForeignKey(ProductORM.id), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey(ProductORM.id), nullable=False)


class GiftCertificateOrderItemORM(CommerceBase):
    """
    Дочерняя item-запись сертификата.

    Здесь хранится ключ активации, который пользователь получает после покупки.
    """

    __tablename__ = "commerce_gift_certificate_order_item"

    order_item_id: Mapped[int] = mapped_column(ForeignKey(OrderItemORM.id), primary_key=True)
    key: Mapped[UUID] = mapped_column(nullable=False, unique=True)


class GiftCertificateUsageORM(CommerceBase):
    """
    Факт использования ключа сертификата пользователем.

    Отдельная таблица нужна, чтобы один и тот же ключ не активировался повторно.
    """

    __tablename__ = "commerce_gift_certificate_usage"
    __table_args__ = (
        UniqueConstraint("order_item_id", "user_id", name="commerce_gift_certificate_usage_order_item_id_user_id_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("commerce_gift_certificate_order_item.order_item_id"), nullable=False, unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = (
    "GiftCertificateORM",
    "GiftCertificateOrderItemORM",
    "GiftCertificateUsageORM",
)
