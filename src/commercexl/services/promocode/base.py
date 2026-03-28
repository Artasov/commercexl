from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import PromocodeDTO, PromocodeDiscountDTO
from commercexl.models import (
    ProductORM,
    PromocodeORM,
    PromocodeProductDiscountORM,
    PromocodeUsageORM,
    commerce_promocode_discounts,
    commerce_promocodeproductdiscount_specific_users,
)
from commercexl.services.base_runtime import BaseRuntime


class Promocode(BaseRuntime):
    """Проверка промокодов и расчёт скидки по их ограничениям."""

    async def serialize_promocode(self, session: AsyncSession, promocode_id: int | None) -> PromocodeDTO | None:
        if promocode_id is None:
            return None
        promocode: PromocodeORM | None = await session.get(PromocodeORM, promocode_id)
        if promocode is None:
            return None
        promocode_id_value = int(promocode.id)
        discounts_query = (
            select(PromocodeProductDiscountORM)
            .join(
                commerce_promocode_discounts,
                commerce_promocode_discounts.c.promocodeproductdiscount_id == PromocodeProductDiscountORM.id,
            )
            .where(commerce_promocode_discounts.c.promocode_id == promocode_id_value)
        )
        discounts = list((await session.execute(discounts_query)).scalars())
        promocode_name = str(promocode.name)
        promocode_code = str(promocode.code)
        promocode_description = str(promocode.description) if promocode.description is not None else None
        promocode_discount_type = str(promocode.discount_type)
        promocode_start_date = promocode.start_date
        promocode_end_date = promocode.end_date
        return PromocodeDTO(
            id=promocode_id_value,
            name=promocode_name,
            code=promocode_code,
            description=promocode_description,
            discount_type=promocode_discount_type,
            start_date=promocode_start_date.isoformat(),
            end_date=promocode_end_date.isoformat() if promocode_end_date else None,
            discounts=[
                PromocodeDiscountDTO(
                    id=discount.id,
                    product=discount.product_id,
                    currency=discount.currency,
                    amount=float(discount.amount),
                    max_usage=discount.max_usage,
                    max_usage_per_user=discount.max_usage_per_user,
                    interval_days=discount.interval_days,
                )
                for discount in discounts
            ],
        )

    async def can_apply(
            self, session: AsyncSession, user_id: int, code: str, product_id: int, currency: str
    ) -> PromocodeDTO:
        """Проверяет применимость промокода и возвращает его DTO для UI."""
        if await session.get(ProductORM, product_id) is None:
            raise self.get_bad_request("Product not found.")
        promocode_query = select(PromocodeORM).where(PromocodeORM.code == code).limit(1)
        promocode: PromocodeORM | None = (await session.execute(promocode_query)).scalar_one_or_none()
        if promocode is None:
            raise self.get_not_found("Promocode not found.")
        promocode_id_value = int(promocode.id)
        await self.calc_promocode_amount(
            session,
            promocode_id_value,
            user_id,
            product_id,
            currency,
            await self.get_product_price(session, product_id, currency) or Decimal("0"),
            raise_only=True,
        )
        payload = await self.serialize_promocode(session, promocode_id_value)
        if payload is None:
            raise self.get_not_found("Promocode not found.")
        return payload

    async def calc_promocode_amount(
            self,
            session: AsyncSession,
            promocode_id: int,
            user_id: int,
            product_id: int,
            currency: str,
            original_amount: Decimal,
            raise_only: bool = False,
    ) -> Decimal:
        """
        Проверяет все ограничения промокода и, если нужно, считает новую сумму.

        `raise_only=True` используется там, где нужно только проверить промокод,
        но не менять цену прямо сейчас.
        """
        promocode: PromocodeORM | None = await session.get(PromocodeORM, promocode_id)
        if promocode is None:
            raise self.get_not_found("Promocode not found.")
        promocode_id_value = int(promocode.id)
        now = datetime.now(UTC)
        if promocode.start_date and now < promocode.start_date:
            raise self.get_bad_request("Promocode not started yet.")
        if promocode.end_date and now > promocode.end_date:
            raise self.get_bad_request("Promocode has expired.")
        discount_query = (
            select(PromocodeProductDiscountORM)
            .join(
                commerce_promocode_discounts,
                commerce_promocode_discounts.c.promocodeproductdiscount_id == PromocodeProductDiscountORM.id,
            )
            .where(
                commerce_promocode_discounts.c.promocode_id == promocode_id_value,
                PromocodeProductDiscountORM.product_id == product_id,
            )
            .limit(1)
        )
        discount = (await session.execute(discount_query)).scalar_one_or_none()
        if discount is None:
            raise self.get_bad_request("Promocode not applicable for this product.")
        if discount.currency != currency:
            raise self.get_bad_request("Promocode not applicable for this currency.")
        specific_users_query = select(func.count()).select_from(commerce_promocodeproductdiscount_specific_users).where(
            commerce_promocodeproductdiscount_specific_users.c.promocodeproductdiscount_id == discount.id,
        )
        has_specific_users = int((await session.execute(specific_users_query)).scalar_one()) > 0
        if has_specific_users:
            allowed_query = select(func.count()).select_from(commerce_promocodeproductdiscount_specific_users).where(
                commerce_promocodeproductdiscount_specific_users.c.promocodeproductdiscount_id == discount.id,
                commerce_promocodeproductdiscount_specific_users.c.user_id == user_id,
            )
            is_allowed = int((await session.execute(allowed_query)).scalar_one()) > 0
            if not is_allowed:
                raise self.get_bad_request("Promocode not applicable for this client.")
        if discount.max_usage is not None:
            # Это глобальный лимит на все использования промокода.
            total_usage_query = select(func.count(PromocodeUsageORM.id)).where(
                PromocodeUsageORM.promocode_id == promocode_id_value,
            )
            if int((await session.execute(total_usage_query)).scalar_one()) >= discount.max_usage:
                raise self.get_bad_request("Promocode usage limit reached.")
        if discount.max_usage_per_user is not None:
            # Это лимит только на одного пользователя.
            user_usage_query = select(func.count(PromocodeUsageORM.id)).where(
                PromocodeUsageORM.promocode_id == promocode_id_value,
                PromocodeUsageORM.user_id == user_id,
            )
            if int((await session.execute(user_usage_query)).scalar_one()) >= discount.max_usage_per_user:
                raise self.get_bad_request("Promocode usage limit for user reached.")
        if discount.interval_days is not None:
            # Некоторые промокоды можно применять повторно только спустя паузу.
            last_usage_query = (
                select(PromocodeUsageORM).where(
                    PromocodeUsageORM.promocode_id == promocode_id_value,
                    PromocodeUsageORM.user_id == user_id,
                )
                .order_by(PromocodeUsageORM.created_at.desc())
                .limit(1)
            )
            last_usage = (await session.execute(last_usage_query)).scalar_one_or_none()
            if last_usage is not None and (now - last_usage.created_at).days < discount.interval_days:
                raise self.get_bad_request("Promocode usage too frequent.")
        if raise_only:
            return original_amount
        if promocode.discount_type == "percentage":
            return original_amount - (original_amount * Decimal(str(discount.amount)) / Decimal("100"))
        if promocode.discount_type == "fixed_amount":
            return max(Decimal("0.00"), original_amount - Decimal(str(discount.amount)))
        return original_amount


