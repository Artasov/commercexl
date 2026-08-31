from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO
from commercexl.models import BalancePaymentORM, OrderORM, PaymentORM, UserCreditsBalanceORM
from commercexl.payment import (
    CheckoutAction,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentState,
    PaymentVerificationResult,
)
from commercexl.services.payment.base import AbstractPaymentService
from commercexl.services.pricing.credits import Credits


class BalancePaymentService(AbstractPaymentService):
    """Синхронная оплата внутренним балансом через общий core finalizer."""

    async def list_options(
            self,
            session: AsyncSession,
            order: OrderORM,
            actor: CommerceUserActorDTO,
    ) -> tuple[PaymentOption, ...]:
        balance = await session.scalar(
            select(UserCreditsBalanceORM).where(UserCreditsBalanceORM.user_id == actor.id),
        )
        credits_cost = Credits.to_credits(
            self.commerce.get_config(),
            order.currency,
            Decimal(order.amount),
        )
        if balance is None or Decimal(balance.amount) < credits_cost:
            return ()
        return (
            PaymentOption(
                id="balance",
                label="Internal balance",
                action_kind="completed",
            ),
        )

    async def create(
            self,
            session: AsyncSession,
            context: PaymentCreateContext,
    ) -> PaymentCreateResult:
        balance_query = (
            select(UserCreditsBalanceORM)
            .where(UserCreditsBalanceORM.user_id == context.actor.id)
            .with_for_update()
        )
        balance = (await session.execute(balance_query)).scalar_one_or_none()
        if balance is None:
            balance = await self.commerce.get_or_create_balance(session, context.actor.id)

        credits_cost = Credits.to_credits(
            self.commerce.get_config(),
            context.order.currency,
            Decimal(context.payment.amount),
        )
        if Decimal(balance.amount) < credits_cost:
            raise self.commerce.get_bad_request("Not enough balance.")

        balance.amount = Decimal(balance.amount) - credits_cost
        balance.updated_at = datetime.now(UTC)
        session.add(BalancePaymentORM(payment_ptr_id=context.payment.id))
        await session.flush()
        return PaymentCreateResult(
            action=CheckoutAction(kind="completed"),
            verification=PaymentVerificationResult(
                state=PaymentState.PAID,
                evidence_key=f"balance:{context.payment.public_id}",
            ),
        )

    async def refund(
            self,
            session: AsyncSession,
            payment,
    ) -> PaymentVerificationResult:
        balance_query = (
            select(UserCreditsBalanceORM)
            .where(UserCreditsBalanceORM.user_id == payment.user_id)
            .with_for_update()
        )
        balance = (await session.execute(balance_query)).scalar_one_or_none()
        if balance is None:
            balance = await self.commerce.get_or_create_balance(session, payment.user_id)
        credits_amount = Credits.to_credits(
            self.commerce.get_config(),
            payment.currency,
            Decimal(payment.amount),
        )
        balance.amount = Decimal(balance.amount) + credits_amount
        balance.updated_at = datetime.now(UTC)
        return PaymentVerificationResult(
            state=PaymentState.REFUNDED,
            evidence_key=f"balance-refund:{payment.public_id}",
        )

    async def cancel(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> PaymentVerificationResult:
        _ = session
        _ = payment
        raise self.commerce.get_conflict("Balance payment cannot be cancelled.")

    async def get_action(
            self,
            session: AsyncSession,
            payment: PaymentORM,
    ) -> CheckoutAction:
        _ = session
        _ = payment
        return CheckoutAction(kind="completed")
