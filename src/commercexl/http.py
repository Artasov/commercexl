from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, CreateOrderDTO, OrderDTO, PaymentDTO, PaymentOptionsDTO, ProductDTO
from commercexl.http_common import load_order_payload
from commercexl.models import EmployeeAvailabilityIntervalORM
from commercexl.payment import CheckoutAction
from commercexl.schemas import (
    ActivateGiftCertificateRequest,
    CreateOrderRequest,
    CreateOrderResponse,
    CreatePaymentAttemptRequest,
    EmployeeAvailabilityRequest,
    EmployeeAvailabilityResponse,
    EmployeeAvailabilityUpdateRequest,
    GiftCertificateActivateResponse,
    GiftCertificateResponse,
    PaymentOptionsResponse,
    PaymentResponse,
    ProductResponse,
    PromocodeCheckRequest,
    PromocodeResponse,
    UserBalanceResponse,
    UserOrderResponse,
)
from commercexl.services.employee.employee import Employee
from commercexl.services.access import OrderAccessAction
from commercexl.services.base_runtime import BaseRuntime
from commercexl.services.products.gift_certificate import GiftCertificate
from commercexl.services.promocode.base import Promocode

PrepareOrderPayload = Callable[
    [AsyncSession, CommerceUserActorDTO, dict[str, Any]],
    Awaitable[dict[str, Any]],
]
PublicProductFilter = Callable[
    [AsyncSession, list[ProductDTO]],
    Awaitable[list[ProductDTO]],
]


@dataclass(frozen=True)
class CommerceHTTPConfig:
    """Auth-neutral dependencies required by the CommerceXL HTTP adapter."""

    get_db_session_dependency: Callable[..., Any]
    get_current_actor_dependency: Callable[..., Any]
    get_mutation_guard_dependency: Callable[..., Any]
    get_commerce_module: Callable[[], Any]
    prepare_order_payload: PrepareOrderPayload | None = None
    filter_public_products: PublicProductFilter | None = None


def create_router(config: CommerceHTTPConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/user/balance/", response_model=UserBalanceResponse, tags=["Commerce / Products"])
    async def user_balance(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ):
        balance = await config.get_commerce_module().create_base_runtime().get_balance(
            session,
            actor.id,
        )
        return {"balance": Decimal(balance.amount) if balance is not None else Decimal("0")}

    @router.get("/balance/product/latest/", response_model=ProductResponse | None, tags=["Commerce / Products"])
    async def latest_balance_product(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            _actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ):
        return await config.get_commerce_module().create_product_serializer().get_latest_balance_product(session)

    @router.get("/products/", response_model=list[ProductResponse], tags=["Commerce / Products"])
    async def list_products(session: AsyncSession = Depends(config.get_db_session_dependency)) -> list[ProductDTO]:
        products = await config.get_commerce_module().create_product_serializer().list_products(session)
        if config.filter_public_products is not None:
            return await config.filter_public_products(session, products)
        return products

    @router.get(
        "/gift-certificates/",
        response_model=list[GiftCertificateResponse],
        tags=["Commerce / Gift Certificates"],
    )
    async def list_gift_certificates(session: AsyncSession = Depends(config.get_db_session_dependency)):
        return await GiftCertificate(config.get_commerce_module()).list(session)

    @router.get(
        "/gift-certificates/{product_id}/",
        response_model=GiftCertificateResponse,
        tags=["Commerce / Gift Certificates"],
    )
    async def gift_certificate_detail(
            product_id: int,
            session: AsyncSession = Depends(config.get_db_session_dependency),
    ):
        return await GiftCertificate(config.get_commerce_module()).get(session, product_id)

    @router.post(
        "/gift-certificate/activate/",
        response_model=GiftCertificateActivateResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Commerce / Gift Certificates"],
    )
    async def activate_gift_certificate(
            payload: ActivateGiftCertificateRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ) -> GiftCertificateActivateResponse:
        await GiftCertificate(config.get_commerce_module()).activate(session, actor.id, payload.key)
        await session.commit()
        return GiftCertificateActivateResponse(detail="Activated.")

    @router.post(
        "/orders/",
        response_model=CreateOrderResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Commerce / Orders"],
    )
    async def create_order(
            payload: CreateOrderRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
            idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    ) -> CreateOrderDTO:
        payload_data = payload.model_dump(exclude_none=True, mode="python")
        if config.prepare_order_payload is not None:
            payload_data = await config.prepare_order_payload(session, actor, payload_data)
        data = await config.get_commerce_module().create_order_runtime().create_order(
            session,
            actor,
            payload_data,
            idempotency_key,
        )
        await session.commit()
        return data

    @router.get("/user/orders/", response_model=list[UserOrderResponse], tags=["Commerce / Orders"])
    async def user_orders(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ) -> list[OrderDTO]:
        return await config.get_commerce_module().create_order_serializer().get_user_orders(
            session,
            actor.id,
        )

    @router.get("/orders/{order_id}/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_detail(
            order_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ) -> OrderDTO:
        runtime = config.get_commerce_module().create_order_runtime()
        order = await runtime.get_order(session, order_id)
        if order is None:
            raise runtime.get_not_found("Order not found.")
        await runtime.check_order_access(session, actor, order, OrderAccessAction.VIEW)
        return await config.get_commerce_module().create_order_serializer().serialize_order(session, order)

    @router.get(
        "/orders/{order_id}/payment-options/",
        response_model=PaymentOptionsResponse,
        tags=["Commerce / Payments"],
    )
    async def payment_options(
            order_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ) -> PaymentOptionsDTO:
        return await config.get_commerce_module().create_payment_runtime().list_payment_options(
            session,
            order_id,
            actor,
        )

    @router.post(
        "/orders/{order_id}/payment-attempts/",
        response_model=PaymentResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Commerce / Payments"],
    )
    async def create_payment_attempt(
            order_id: UUID,
            payload: CreatePaymentAttemptRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
            idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    ) -> PaymentDTO:
        data = await config.get_commerce_module().create_payment_runtime().create_attempt(
            session,
            order_id,
            payload.payment_option_id,
            actor,
            idempotency_key,
        )
        await session.commit()
        return data

    @router.get(
        "/payments/{payment_public_id}/",
        response_model=PaymentResponse,
        tags=["Commerce / Payments"],
    )
    async def payment_status(
            payment_public_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ) -> PaymentDTO:
        return await config.get_commerce_module().create_payment_runtime().get_payment_status(
            session,
            payment_public_id,
            actor,
        )

    @router.post(
        "/payments/{payment_public_id}/checkout-action/",
        response_model=CheckoutAction,
        tags=["Commerce / Payments"],
    )
    async def issue_checkout_action(
            payment_public_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ) -> CheckoutAction:
        action = await config.get_commerce_module().create_payment_runtime().issue_checkout_action(
            session,
            payment_public_id,
            actor,
        )
        await session.commit()
        return action

    @router.post("/orders/{order_id}/cancel/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_cancel(
            order_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ) -> OrderDTO:
        service = config.get_commerce_module().create_order_runtime()
        data = await service.cancel_order(session, order_id, actor)
        await session.commit()
        return data

    @router.post("/orders/{order_id}/refund/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_refund(
            order_id: UUID,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ) -> OrderDTO:
        runtime = config.get_commerce_module().create_payment_runtime()
        await runtime.refund_order(session, order_id, actor)
        await session.commit()
        return await load_order_payload(
            session,
            order_id,
            config.get_commerce_module().create_order_runtime(),
        )

    @router.post("/promocode/applicable/", response_model=PromocodeResponse, tags=["Commerce / Promocodes"])
    async def promocode_applicable(
            payload: PromocodeCheckRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ):
        return await Promocode(commerce_module=config.get_commerce_module()).can_apply(
            session,
            actor.id,
            payload.promocode,
            payload.product,
            payload.currency,
        )

    @router.get(
        "/employee/availability/",
        response_model=list[EmployeeAvailabilityResponse],
        tags=["Commerce / Employees"],
    )
    async def list_employee_availability(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
    ):
        if not actor.has_permission("commerce.manage"):
            raise BaseRuntime.get_not_found("Availability not found.")
        return await Employee().list_employee_availability(session, actor.id)

    @router.post(
        "/employee/availability/",
        response_model=EmployeeAvailabilityResponse,
        tags=["Commerce / Employees"],
    )
    async def create_employee_availability(
            payload: EmployeeAvailabilityRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ):
        if not actor.has_permission("commerce.manage"):
            raise BaseRuntime.get_not_found("Availability not found.")
        data = await Employee().create_employee_availability(session, actor.id, payload.start, payload.end)
        await session.commit()
        return data

    @router.put(
        "/employee/availability/{interval_id}/",
        response_model=EmployeeAvailabilityResponse,
        tags=["Commerce / Employees"],
    )
    async def update_employee_availability(
            interval_id: int,
            payload: EmployeeAvailabilityUpdateRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ):
        if not actor.has_permission("commerce.manage"):
            raise BaseRuntime.get_not_found("Availability not found.")
        current_item = await session.get(EmployeeAvailabilityIntervalORM, interval_id)
        if current_item is None or current_item.user_id != actor.id:
            raise BaseRuntime.get_not_found("Availability interval not found.")
        data = await Employee().update_employee_availability(
            session,
            actor.id,
            interval_id,
            payload.start or current_item.start,
            payload.end or current_item.end,
        )
        await session.commit()
        return data

    @router.delete(
        "/employee/availability/{interval_id}/",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Commerce / Employees"],
    )
    async def delete_employee_availability(
            interval_id: int,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            actor: CommerceUserActorDTO = Depends(config.get_current_actor_dependency),
            _guard: Any = Depends(config.get_mutation_guard_dependency),
    ) -> Response:
        if not actor.has_permission("commerce.manage"):
            raise BaseRuntime.get_not_found("Availability not found.")
        await Employee().delete_employee_availability(session, actor.id, interval_id)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
