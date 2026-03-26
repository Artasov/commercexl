from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.models import BalancePaymentORM, OrderORM, PaymentORM
from commercexl.services.payment.base import AbstractPaymentService
from commercexl.services.pricing.credits import Credits


class BalancePaymentService(AbstractPaymentService):
    """РћРїР»Р°С‚Р° РІРЅСѓС‚СЂРµРЅРЅРёРј Р±Р°Р»Р°РЅСЃРѕРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""

    payment_system = "balance"
    payment_kind = "balancepayment"
    blocks_order_cancellation = True

    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            amount: Decimal,
            request_base_url: str,
    ) -> PaymentORM:
        _ = request_base_url
        if order.user_id is None:
            raise self.commerce.get_bad_request("User not found.")

        balance = await self.commerce.get_or_create_balance(session, order.user_id)
        credits_cost = Credits.to_credits(self.commerce.get_config(), order.currency, amount)
        if Decimal(str(balance.amount)) < credits_cost:
            raise self.commerce.get_bad_request("Not enough balance.")

        now = datetime.now(UTC)
        balance.amount = Decimal(str(balance.amount)) - credits_cost
        balance.updated_at = now

        payment = await self.create_parent_payment(
            session,
            order=order,
            amount=amount,
            is_paid=True,
            payment_url=None,
        )
        session.add(BalancePaymentORM(payment_ptr_id=payment.id))

        order.payment_id = payment.id
        order.is_inited = True
        order.is_paid = True
        order.updated_at = now

        await self.commerce.create_order_runtime().execute_order(session, order)
        return payment

    async def is_paid(self, session: AsyncSession, payment_id: int) -> bool:
        payment = await session.get(PaymentORM, payment_id)
        return bool(payment and payment.is_paid)

    async def get_pay_link(self, session: AsyncSession, payment_id: int) -> str | None:
        payment = await session.get(PaymentORM, payment_id)
        return str(payment.payment_url) if payment and payment.payment_url is not None else None

    async def refund(self, session: AsyncSession, order: OrderORM, payment: PaymentORM) -> None:
        if order.user_id is None:
            raise self.commerce.get_bad_request("User not found.")

        credits_amount = Credits.to_credits(self.commerce.get_config(), order.currency, Decimal(str(order.amount or 0)))
        balance = await self.commerce.get_or_create_balance(session, order.user_id)
        now = datetime.now(UTC)
        balance.amount = Decimal(str(balance.amount)) + credits_amount
        balance.updated_at = now
        payment.updated_at = now


