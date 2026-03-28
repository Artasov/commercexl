from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import PaymentDTO
from commercexl.models import PaymentORM
from commercexl.services.base_runtime import BaseRuntime


class PaymentSerializer(BaseRuntime):
    """Сериализация оплаты для API."""

    async def serialize_payment(self, session: AsyncSession, payment_id: int) -> PaymentDTO:
        payment: PaymentORM | None = await session.get(PaymentORM, payment_id)
        if payment is None:
            raise self.get_not_found("Payment not found.")

        payment_db_id = int(payment.id)
        payment_service = self.payment_registry.get_service_by_kind(payment.kind)
        extras = await payment_service.get_extras(session, payment_db_id) if payment_service is not None else None
        payment_url = (
            await payment_service.get_pay_link(session, payment_db_id)
            if payment_service is not None
            else (str(payment.payment_url) if payment.payment_url is not None else None)
        )
        return PaymentDTO(
            id=payment_db_id,
            amount=float(payment.amount),
            currency=str(payment.currency),
            payment_url=payment_url,
            created_at=payment.created_at.isoformat(),
            extras=extras,
        )


