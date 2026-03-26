from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import PaymentDTO
from commercexl.models import OrderORM, PaymentORM
from commercexl.services.base_runtime import BaseRuntime


class PaymentRuntime(BaseRuntime):
    """РЎРѕР·РґР°С‘С‚ РѕРїР»Р°С‚Сѓ РЅСѓР¶РЅРѕРіРѕ С‚РёРїР° Рё РїСЂРёРІСЏР·С‹РІР°РµС‚ РµС‘ Рє Р·Р°РєР°Р·Сѓ."""

    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            request_base_url: str,
    ) -> PaymentORM | None:
        """
        РЎРѕР·РґР°С‘С‚ РґРѕС‡РµСЂРЅСЋСЋ Р·Р°РїРёСЃСЊ РѕРїР»Р°С‚С‹ С‡РµСЂРµР· СЃРµСЂРІРёСЃ РІС‹Р±СЂР°РЅРЅРѕР№ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃРёСЃС‚РµРјС‹.

        РЎР°Рј `PaymentRuntime` РЅРµ Р·РЅР°РµС‚ РґРµС‚Р°Р»РµР№ РєРѕРЅРєСЂРµС‚РЅРѕР№ РѕРїР»Р°С‚С‹.
        РћРЅ С‚РѕР»СЊРєРѕ РЅР°С…РѕРґРёС‚ РЅСѓР¶РЅС‹Р№ payment-СЃРµСЂРІРёСЃ РІ registry Рё РґР°С‘С‚ РµРјСѓ Р·Р°РєР°Р·.
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
        """РРЅРёС†РёР°Р»РёР·РёСЂСѓРµС‚ РѕРїР»Р°С‚Сѓ РґР»СЏ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ Р·Р°РєР°Р·Р° С‡РµСЂРµР· РїСѓР±Р»РёС‡РЅС‹Р№ endpoint."""
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
        """Р—Р°РїСѓСЃРєР°РµС‚ РІРѕР·РІСЂР°С‚ С‡РµСЂРµР· payment-service, РєРѕС‚РѕСЂС‹Р№ РїСЂРёРІСЏР·Р°РЅ Рє СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµР№ РѕРїР»Р°С‚Рµ Р·Р°РєР°Р·Р°."""
        if order.payment_id is None:
            raise self.get_bad_request("Order payment not found.")

        payment = await session.get(PaymentORM, order.payment_id)
        if payment is None:
            raise self.get_not_found("Payment not found.")

        payment_service = self.payment_registry.get_service_by_kind(payment.kind)
        if payment_service is None:
            raise self.get_bad_request("Unknown payment system.")

        await payment_service.refund(session, order, payment)


