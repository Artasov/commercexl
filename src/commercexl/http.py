from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import CommerceUserActorDTO, CreateOrderDTO, CreateOrderIdOnlyDTO, OrderDTO
from commercexl.http_common import get_base_url, load_order_payload
from commercexl.models import EmployeeAvailabilityIntervalORM
from commercexl.schemas import (
    CreateOrderIdOnlyResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    EmployeeAvailabilityRequest,
    EmployeeAvailabilityResponse,
    EmployeeAvailabilityUpdateRequest,
    InitPaymentRequest,
    PaymentResponse,
    PaymentTypesResponse,
    ProductResponse,
    PromocodeCheckRequest,
    PromocodeResponse,
    UserBalanceResponse,
    UserOrderResponse,
)
from commercexl.services.employee.employee import Employee
from commercexl.services.promocode.base import Promocode

UserObject = Any
PrepareOrderContext = Callable[
    [AsyncSession, UserObject, dict[str, Any]],
    Awaitable[tuple[CommerceUserActorDTO, dict[str, Any]]],
]


@dataclass(frozen=True)
class CommerceHTTPConfig:
    get_db_session_dependency: Callable[..., Any]
    get_current_user_dependency: Callable[..., Any]
    get_commerce_module: Callable[[], Any]
    build_actor: Callable[[UserObject], CommerceUserActorDTO]
    get_user_id: Callable[[UserObject], int]
    is_staff: Callable[[UserObject], bool]
    prepare_order_context: PrepareOrderContext | None = None
    return_debug_stub: Callable[[], bool] = lambda: False


async def get_default_order_context(
        session: AsyncSession,
        user: UserObject,
        payload: dict[str, Any],
        *,
        build_actor: Callable[[UserObject], CommerceUserActorDTO],
) -> tuple[CommerceUserActorDTO, dict[str, Any]]:
    _ = session
    return build_actor(user), payload


def create_router(config: CommerceHTTPConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/user/balance/", response_model=UserBalanceResponse, tags=["Commerce / Products"])
    async def user_balance(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ):
        balance = await config.get_commerce_module().create_base_runtime().get_or_create_balance(
            session, config.get_user_id(user),
        )
        await session.commit()
        return {"balance": float(balance.amount)}

    @router.get("/balance/product/latest/", response_model=ProductResponse | None, tags=["Commerce / Products"])
    async def latest_balance_product(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            _: UserObject = Depends(config.get_current_user_dependency),
    ):
        return await config.get_commerce_module().create_product_serializer().get_latest_balance_product(session)

    @router.get("/products/", response_model=list[ProductResponse], tags=["Commerce / Products"])
    async def list_products(session: AsyncSession = Depends(config.get_db_session_dependency)):
        return await config.get_commerce_module().create_product_serializer().list_products(session)

    @router.get("/payment/types/", response_model=PaymentTypesResponse, tags=["Commerce / Products"])
    async def payment_types(_: UserObject = Depends(config.get_current_user_dependency)):
        return await config.get_commerce_module().create_base_runtime().get_payment_types()

    @router.post(
        "/orders/create/",
        response_model=CreateOrderIdOnlyResponse | CreateOrderResponse | str,
        status_code=status.HTTP_201_CREATED,
        tags=["Commerce / Orders"],
    )
    async def create_order(
            payload: CreateOrderRequest,
            request: Request,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> CreateOrderIdOnlyDTO | CreateOrderDTO | str:
        payload_data = payload.model_dump(exclude_none=True)
        if config.prepare_order_context is None:
            actor, payload_data = await get_default_order_context(
                session, user, payload_data, build_actor=config.build_actor,
            )
        else:
            actor, payload_data = await config.prepare_order_context(session, user, payload_data)

        order_runtime = config.get_commerce_module().create_order_runtime()
        data = await order_runtime.create_order(session, actor, payload_data, get_base_url(request))
        await session.commit()
        if config.return_debug_stub():
            return "/something-go-wrong"
        return data

    @router.get("/user/orders/", response_model=list[UserOrderResponse], tags=["Commerce / Orders"])
    async def user_orders(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> list[OrderDTO]:
        return await config.get_commerce_module().create_order_serializer().get_user_orders(
            session, config.get_user_id(user),
        )

    @router.get("/orders/{order_id}/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_detail(
            order_id: str,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> OrderDTO:
        order_service = config.get_commerce_module().create_order_runtime()
        order = await order_service.get_order(session, order_id)
        if order is None or (not config.is_staff(user) and order.user_id != config.get_user_id(user)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        return await config.get_commerce_module().create_order_serializer().serialize_order(session, order)

    @router.post("/orders/{order_id}/cancel/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_cancel(
            order_id: str,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> OrderDTO:
        service = config.get_commerce_module().create_order_runtime()
        order = await service.get_order(session, order_id)
        if order is None or order.user_id != config.get_user_id(user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        await service.cancel_order(session, order)
        await session.commit()
        return await load_order_payload(session, order_id, service)

    @router.post("/orders/{order_id}/execute/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_execute(
            order_id: str,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> OrderDTO:
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        service = config.get_commerce_module().create_order_runtime()
        order = await service.get_order(session, order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        await service.execute_order(session, order)
        await session.commit()
        return await load_order_payload(session, order_id, service)

    @router.post("/orders/{order_id}/refund/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_refund(
            order_id: str,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> OrderDTO:
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        service = config.get_commerce_module().create_order_runtime()
        order = await service.get_order(session, order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        await service.refund_order(session, order)
        await session.commit()
        return await load_order_payload(session, order_id, service)

    @router.post("/orders/{order_id}/delete/", tags=["Commerce / Orders"])
    async def order_delete(
            order_id: str,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> bool:
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        order = await config.get_commerce_module().create_order_runtime().get_order(session, order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        await session.delete(order)
        await session.commit()
        return True

    @router.post("/orders/{order_id}/init/{init_payment}/", response_model=UserOrderResponse, tags=["Commerce / Orders"])
    async def order_init(
            order_id: str,
            init_payment: int,
            request: Request,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> OrderDTO:
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        service = config.get_commerce_module().create_order_runtime()
        order = await service.get_order(session, order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        await service.init_existing_order(session, order, get_base_url(request), bool(init_payment))
        await session.commit()
        return await load_order_payload(session, order_id, service)

    @router.post("/orders/{order_id}/resend_payment_notification/", tags=["Commerce / Orders"])
    async def resend_payment_notification(
            order_id: str,
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> None:
        _ = order_id
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment system not found.")

    @router.post("/orders/{order_id}/init-payment/", response_model=PaymentResponse, tags=["Commerce / Payments"])
    async def init_payment(
            order_id: str,
            payload: InitPaymentRequest,
            request: Request,
            session: AsyncSession = Depends(config.get_db_session_dependency),
    ):
        service = config.get_commerce_module().create_payment_runtime()
        order = await service.get_order(session, order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
        data = await service.init_payment(session, order, payload.model_dump(), get_base_url(request))
        await session.commit()
        return data

    @router.post("/promocode/applicable/", response_model=PromocodeResponse, tags=["Commerce / Promocodes"])
    async def promocode_applicable(
            payload: PromocodeCheckRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ):
        return await Promocode(commerce_module=config.get_commerce_module()).can_apply(
            session, config.get_user_id(user), payload.promocode, payload.product, payload.currency,
        )

    @router.get("/employee/availability/", response_model=list[EmployeeAvailabilityResponse], tags=["Commerce / Employees"])
    async def list_employee_availability(
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ):
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        return await Employee().list_employee_availability(session, config.get_user_id(user))

    @router.post("/employee/availability/", response_model=EmployeeAvailabilityResponse, tags=["Commerce / Employees"])
    async def create_employee_availability(
            payload: EmployeeAvailabilityRequest,
            session: AsyncSession = Depends(config.get_db_session_dependency),
            user: UserObject = Depends(config.get_current_user_dependency),
    ):
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        data = await Employee().create_employee_availability(
            session, config.get_user_id(user), payload.start, payload.end,
        )
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
            user: UserObject = Depends(config.get_current_user_dependency),
    ):
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        current_item: EmployeeAvailabilityIntervalORM | None = await session.get(
            EmployeeAvailabilityIntervalORM, interval_id,
        )
        if current_item is None or current_item.user_id != config.get_user_id(user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability interval not found.")
        start = payload.start or current_item.start
        end = payload.end or current_item.end
        data = await Employee().update_employee_availability(
            session, config.get_user_id(user), interval_id, start, end,
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
            user: UserObject = Depends(config.get_current_user_dependency),
    ) -> Response:
        if not config.is_staff(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        await Employee().delete_employee_availability(session, config.get_user_id(user), interval_id)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


__all__ = ("CommerceHTTPConfig", "create_router")


