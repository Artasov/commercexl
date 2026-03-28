from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import PaymentDTO
from commercexl.models import OrderORM, PaymentORM
from commercexl.services.base_runtime import BaseRuntime


class PaymentRuntime(BaseRuntime):
    """Создаёт оплату нужного типа и привязывает её к заказу."""

    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            request_base_url: str,
    ) -> PaymentORM | None:
        """
        Создаёт дочернюю запись оплаты через сервис выбранной платёжной системы.

        Сам `PaymentRuntime` не знает деталей конкретной оплаты.
        Он только находит нужный payment-сервис в registry и даёт ему заказ.
        """
        amount = Decimal(str(order.amount or 0))
        payment_service = self.payment_registry.get_service_by_system(order.payment_system)
        if payment_service is None:
            return None

        payment = await payment_service.create(session, order, amount, request_base_url)
        order.payment_id = payment.id
        order.is_inited = True
        order.updated_at = payment.updated_at
        await session.flush()
        return payment

    async def init_payment(
            self,
            session: AsyncSession,
            order: OrderORM,
            payload: dict[str, Any],
            request_base_url: str,
    ) -> PaymentDTO:
        """Инициализирует оплату для уже существующего заказа через публичный endpoint."""
        payment_serializer = self.create_payment_serializer()
        if order.is_paid:
            raise self.get_bad_request("Order already paid.")
        if order.payment_id:
            return await payment_serializer.serialize_payment(session, order.payment_id)

        self.validate_payment_system(payload["currency"], payload["payment_system"])
        order.payment_system = payload["payment_system"]
        order.currency = payload["currency"]
        order.amount = Decimal(str(payload["amount"]))
        payment = await self.create(session, order, request_base_url)
        if payment is None:
            raise self.get_bad_request("Unknown payment system.")
        return await payment_serializer.serialize_payment(session, payment.id)

    async def refund(self, session: AsyncSession, order: OrderORM) -> None:
        """Запускает возврат через payment-service, который привязан к уже существующей оплате заказа."""
        if order.payment_id is None:
            raise self.get_bad_request("Order payment not found.")

        payment = await session.get(PaymentORM, order.payment_id)
        if payment is None:
            raise self.get_not_found("Payment not found.")

        payment_service = self.payment_registry.get_service_by_kind(payment.kind)
        if payment_service is None:
            raise self.get_bad_request("Unknown payment system.")

        await payment_service.refund(session, order, payment)


