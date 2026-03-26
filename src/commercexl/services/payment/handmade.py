from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.models import HandMadePaymentORM, OrderORM, PaymentORM
from commercexl.services.payment.base import AbstractPaymentService


class HandMadePaymentService(AbstractPaymentService):
    """Р СѓС‡РЅР°СЏ РѕРїР»Р°С‚Р° Р±РµР· РІРЅРµС€РЅРµРіРѕ РїСЂРѕРІР°Р№РґРµСЂР°."""

    payment_system = "handmade"
    payment_kind = "handmadepayment"

    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            amount: Decimal,
            request_base_url: str,
    ) -> PaymentORM:
        _ = request_base_url
        payment = await self.create_parent_payment(
            session,
            order=order,
            amount=amount,
            is_paid=False,
            payment_url=None,
        )
        session.add(HandMadePaymentORM(payment_ptr_id=payment.id))
        return payment

    async def is_paid(self, session: AsyncSession, payment_id: int) -> bool:
        payment = await session.get(PaymentORM, payment_id)
        return bool(payment and payment.is_paid)

    async def get_pay_link(self, session: AsyncSession, payment_id: int) -> str | None:
        payment = await session.get(PaymentORM, payment_id)
        return str(payment.payment_url) if payment and payment.payment_url is not None else None

    async def refund(self, session: AsyncSession, order: OrderORM, payment: PaymentORM) -> None:
        _ = session
        _ = order
        payment.updated_at = datetime.now(UTC)


