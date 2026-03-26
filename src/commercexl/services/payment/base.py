from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from inspect import isabstract
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import OrderDTO
from commercexl.models import OrderORM, PaymentORM

if TYPE_CHECKING:
    from commercexl.services.base_runtime import BaseRuntime


class AbstractPaymentService(ABC):
    """
    РђР±СЃС‚СЂР°РєС‚РЅС‹Р№ СЃРµСЂРІРёСЃ РѕРґРЅРѕРіРѕ СЃРїРѕСЃРѕР±Р° РѕРїР»Р°С‚С‹.

    РџРѕС‚РѕРјРѕРє СЌС‚РѕРіРѕ РєР»Р°СЃСЃР° РѕРїРёСЃС‹РІР°РµС‚ РѕРґРЅСѓ РїР»Р°С‚С‘Р¶РЅСѓСЋ СЃРёСЃС‚РµРјСѓ РІРЅСѓС‚СЂРё `commerce`.

    payment_system:
    Р’РЅСѓС‚СЂРµРЅРЅРµРµ РёРјСЏ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃРёСЃС‚РµРјС‹ РЅР° СѓСЂРѕРІРЅРµ API Рё Р·Р°РєР°Р·Р°.
    РРјРµРЅРЅРѕ СЌС‚Рѕ Р·РЅР°С‡РµРЅРёРµ РїСЂРёС…РѕРґРёС‚ РІ `OrderORM.payment_system`
    Рё РёРјРµРЅРЅРѕ РїРѕ РЅРµРјСѓ `PaymentRegistry` РёС‰РµС‚ РЅСѓР¶РЅС‹Р№ payment-service.

    payment_kind:
    Р—РЅР°С‡РµРЅРёРµ РґР»СЏ `PaymentORM.kind`.
    РќСѓР¶РµРЅ, С‡С‚РѕР±С‹ РїРѕС‚РѕРј РїРѕ СѓР¶Рµ СЃРѕР·РґР°РЅРЅРѕР№ Р·Р°РїРёСЃРё РѕРїР»Р°С‚С‹ РїРѕРЅСЏС‚СЊ,
    РєР°РєРѕР№ payment-service РµС‘ РѕР±СЃР»СѓР¶РёРІР°РµС‚.

    blocks_order_cancellation:
    РџРѕРєР°Р·С‹РІР°РµС‚, РјРѕР¶РЅРѕ Р»Рё РѕС‚РјРµРЅСЏС‚СЊ Р·Р°РєР°Р·, РµСЃР»Рё Сѓ РЅРµРіРѕ СѓР¶Рµ РµСЃС‚СЊ С‚Р°РєР°СЏ РѕРїР»Р°С‚Р°.
    Р•СЃР»Рё `True`, С‚Рѕ `commerce` РЅРµ РґР°СЃС‚ РѕС‚РјРµРЅРёС‚СЊ Р·Р°РєР°Р· РѕР±С‹С‡РЅС‹Рј СЃРїРѕСЃРѕР±РѕРј.

    РћР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РјРµС‚РѕРґС‹:

    create():
    РЎРѕР·РґР°С‘С‚ РѕРїР»Р°С‚Сѓ СЌС‚РѕРіРѕ С‚РёРїР°.
    Р—РґРµСЃСЊ payment-service СЃР°Рј СЃРѕР·РґР°С‘С‚ СЂРѕРґРёС‚РµР»СЊСЃРєСѓСЋ `PaymentORM`
    Рё РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё СЃРІРѕСЋ РґРѕС‡РµСЂРЅСЋСЋ Р·Р°РїРёСЃСЊ РѕРїР»Р°С‚С‹.

    is_paid():
    РџСЂРѕРІРµСЂСЏРµС‚, СЃС‡РёС‚Р°РµС‚СЃСЏ Р»Рё СЌС‚Р° РѕРїР»Р°С‚Р° РѕРїР»Р°С‡РµРЅРЅРѕР№.

    РќРµРѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РјРµС‚РѕРґС‹:

    get_pay_link():
    Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃСЃС‹Р»РєСѓ РЅР° РѕРїР»Р°С‚Сѓ, РµСЃР»Рё РѕРЅР° Сѓ СЌС‚РѕРіРѕ С‚РёРїР° РѕРїР»Р°С‚С‹ РІРѕРѕР±С‰Рµ РµСЃС‚СЊ.

    get_extras():
    Р’РѕР·РІСЂР°С‰Р°РµС‚ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РїРѕР»СЏ РѕРїР»Р°С‚С‹ РґР»СЏ API.

    РњРѕР¶РЅРѕ РїРµСЂРµРѕРїСЂРµРґРµР»РёС‚СЊ РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё:

    create_parent_payment():
    Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Р№ РјРµС‚РѕРґ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ Р±Р°Р·РѕРІРѕР№ `PaymentORM`.
    РћР±С‹С‡РЅРѕ РµРіРѕ С…РІР°С‚Р°РµС‚ РєР°Рє РµСЃС‚СЊ, РЅРѕ РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё РјРѕР¶РЅРѕ РїРµСЂРµРѕРїСЂРµРґРµР»РёС‚СЊ.
    """

    payment_system: str = ""
    payment_kind: str = ""
    blocks_order_cancellation = False

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if isabstract(cls):
            return
        if not str(getattr(cls, "payment_system", "")).strip():
            raise TypeError(f"{cls.__name__} must define 'payment_system'.")
        if not str(getattr(cls, "payment_kind", "")).strip():
            raise TypeError(f"{cls.__name__} must define 'payment_kind'.")

    def __init__(self, commerce: "BaseRuntime") -> None:
        self.commerce = commerce

    @abstractmethod
    async def create(
            self,
            session: AsyncSession,
            order: OrderORM,
            amount: Decimal,
            request_base_url: str,
    ) -> PaymentORM:
        raise NotImplementedError

    @abstractmethod
    async def is_paid(self, session: AsyncSession, payment_id: int) -> bool:
        raise NotImplementedError

    async def refund(self, session: AsyncSession, order: OrderORM, payment: PaymentORM) -> None:
        _ = session
        _ = order
        _ = payment
        raise self.commerce.get_bad_request("Payment refund is not supported.")

    async def create_parent_payment(
            self,
            session: AsyncSession,
            *,
            order: OrderORM,
            amount: Decimal,
            is_paid: bool,
            payment_url: str | None,
    ) -> PaymentORM:
        payment = PaymentORM(
            user_id=order.user_id,
            amount=amount,
            currency=order.currency,
            payment_url=payment_url,
            is_paid=is_paid,
            kind=self.payment_kind,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(payment)
        await session.flush()
        return payment

    def has_payment_system(self, payment_system: str | None) -> bool:
        normalized_system = str(payment_system or "").strip().lower()
        return normalized_system == self.payment_system.lower()

    def has_payment_kind(self, payment_kind: str | None) -> bool:
        normalized_kind = str(payment_kind or "").strip().lower()
        return normalized_kind == self.payment_kind.lower()

    async def get_extras(self, session: AsyncSession, payment_id: int) -> dict[str, Any] | None:
        _ = session
        _ = payment_id
        return None

    async def get_pay_link(self, session: AsyncSession, payment_id: int) -> str | None:
        payment = await session.get(PaymentORM, payment_id)
        return str(payment.payment_url) if payment and payment.payment_url is not None else None

    async def finalize_paid_order(self, session: AsyncSession, order: OrderORM) -> OrderDTO:
        """
        РРґРµРјРїРѕС‚РµРЅС‚РЅРѕ Р·Р°РІРµСЂС€Р°РµС‚ Р·Р°РєР°Р· РїРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РѕРїР»Р°С‚С‹.

        РџРѕРІС‚РѕСЂРЅС‹Р№ callback РёР»Рё РїРѕРІС‚РѕСЂРЅР°СЏ СЂСѓС‡РЅР°СЏ РїСЂРѕРІРµСЂРєР° РЅРµ РґРѕР»Р¶РЅС‹ РїРѕРІС‚РѕСЂРЅРѕ РІС‹РїРѕР»РЅСЏС‚СЊ Р·Р°РєР°Р·.
        РџРѕСЌС‚РѕРјСѓ Р·РґРµСЃСЊ:
        - РѕРїР»Р°С‚Р° РїРѕРјРµС‡Р°РµС‚СЃСЏ СѓСЃРїРµС€РЅРѕР№ С‚РѕР»СЊРєРѕ РѕРґРёРЅ СЂР°Р·;
        - `execute_order()` РІС‹Р·С‹РІР°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ РµСЃР»Рё Р·Р°РєР°Р· РµС‰С‘ РЅРµ РІС‹РїРѕР»РЅРµРЅ;
        - РІ РѕС‚РІРµС‚ РІСЃРµРіРґР° РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ Р°РєС‚СѓР°Р»СЊРЅС‹Р№ `OrderDTO`.
        """
        if order.is_cancelled:
            return await self.commerce.create_order_serializer().serialize_order(session, order)

        if not order.is_paid:
            order.is_paid = True
            order.updated_at = datetime.now(UTC)

        if not order.is_executed and not order.is_refunded:
            await self.commerce.create_order_runtime().execute_order(session, order)

        await session.flush()
        return await self.commerce.create_order_serializer().serialize_order(session, order)


class AbstractCallbackPaymentService(AbstractPaymentService, ABC):
    """
    Р‘Р°Р·РѕРІС‹Р№ СЃРµСЂРІРёСЃ РѕРїР»Р°С‚С‹, Сѓ РєРѕС‚РѕСЂРѕР№ РµСЃС‚СЊ callback РёР»Рё СЂСѓС‡РЅР°СЏ РїСЂРѕРІРµСЂРєР°.

    РћР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РјРµС‚РѕРґС‹:

    confirm():
    РџРѕРґС‚РІРµСЂР¶РґР°РµС‚ РѕРїР»Р°С‚Сѓ РїРѕ РІС…РѕРґСЏС‰РёРј РґР°РЅРЅС‹Рј РїСЂРѕРІР°Р№РґРµСЂР°.
    РћР±С‹С‡РЅРѕ РІС‹Р·С‹РІР°РµС‚СЃСЏ РёР· callback endpoint, РєРѕРіРґР° РїСЂРѕРІР°Р№РґРµСЂ СѓР¶Рµ РїСЂРёСЃР»Р°Р» РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ.

    check():
    Р СѓС‡РЅР°СЏ РїСЂРѕРІРµСЂРєР° РѕРїР»Р°С‚С‹.
    РћР±С‹С‡РЅРѕ РІС‹Р·С‹РІР°РµС‚СЃСЏ, РєРѕРіРґР° РїСЂРѕРµРєС‚ СЃР°Рј РёРґС‘С‚ РІРѕ РІРЅРµС€РЅРёР№ СЃРµСЂРІРёСЃ Рё С…РѕС‡РµС‚ РїРѕРЅСЏС‚СЊ, РїСЂРѕС€Р»Р° РѕРїР»Р°С‚Р° РёР»Рё РЅРµС‚.
    """

    @abstractmethod
    async def confirm(self, session: AsyncSession, data: dict[str, Any]) -> OrderDTO:
        raise NotImplementedError

    @abstractmethod
    async def check(self, session: AsyncSession, data: dict[str, Any]) -> OrderDTO:
        raise NotImplementedError


