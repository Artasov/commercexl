from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import PaymentDTO
from commercexl.models import PaymentORM
from commercexl.payment import CheckoutAction
from commercexl.services.base_runtime import BaseRuntime


class PaymentSerializer(BaseRuntime):
    """Сериализует только provider-neutral canonical attempt fields."""

    async def serialize_payment(
            self,
            session: AsyncSession,
            payment: PaymentORM | int,
            *,
            action: CheckoutAction | None = None,
    ) -> PaymentDTO:
        payment_record = (
            payment
            if isinstance(payment, PaymentORM)
            else await session.get(PaymentORM, payment)
        )
        if payment_record is None:
            raise self.get_not_found("Payment not found.")

        if action is not None and action.kind != payment_record.action_kind:
            raise TypeError("Issued checkout action does not match the payment attempt.")
        return PaymentDTO(
            id=payment_record.public_id,
            order_id=payment_record.order_id,
            attempt_no=payment_record.attempt_no,
            amount=payment_record.amount,
            currency=payment_record.currency,
            payment_system=payment_record.payment_system,
            provider_kind=payment_record.kind,
            payment_option_id=payment_record.payment_option_id,
            state=payment_record.payment_state,
            action=action,
            reason_code=payment_record.reason_code,
            revision=payment_record.revision,
            expires_at=self.as_utc(payment_record.expires_at),
            created_at=self.as_utc(payment_record.created_at),
            updated_at=self.as_utc(payment_record.updated_at),
        )

    @staticmethod
    def as_utc(value: datetime | None) -> datetime | None:
        """Нормализует timezone-aware UTC также для SQLite test adapter."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
