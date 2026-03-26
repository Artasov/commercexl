from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from commercexl import (
    BalanceOrderItemService,
    BaseConfig,
    CommerceHTTPConfig,
    CommerceModule,
    CommerceUserActorDTO,
    OrderORM,
    create_router,
    get_default_commerce_module,
)


class TestConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("100")}


def test_default_commerce_module_registers_balance_order_item_service():
    commerce = get_default_commerce_module()
    handler = commerce.create_base_runtime().product_registry.get_handler_by_kind("balance")

    assert handler is not None
    assert handler.get_order_item_service_class() is BalanceOrderItemService


def test_commerce_module_raises_without_registered_payment_service():
    class BrokenConfig(BaseConfig):
        PAYMENT_SYSTEMS = {"USD": ("handmade", "missing")}
        MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
        CREDITS_CONVERTERS = {"USD": Decimal("100")}

    try:
        CommerceModule(
            config_class=BrokenConfig,
            payments=type("EmptyPaymentBuilder", (), {"get_registered_systems": lambda self: {"handmade"}})(),
        )
    except TypeError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("CommerceModule must reject unknown payment services in config.")


def test_http_router_factory_builds_routes_without_project_dependencies():
    class FakeBaseRuntime:
        async def get_or_create_balance(self, session, user_id):
            _ = session
            _ = user_id
            return SimpleNamespace(amount=Decimal("42"))

        async def get_payment_types(self):
            return {"USD": ["handmade"]}

    class FakeProductSerializer:
        async def get_latest_balance_product(self, session):
            _ = session
            return None

        async def list_products(self, session):
            _ = session
            return []

    class FakeOrderRuntime:
        async def create_order(self, session, actor, payload, request_base_url):
            _ = session
            _ = actor
            _ = payload
            _ = request_base_url
            return {"id": str(uuid4())}

        async def get_order(self, session, order_id):
            _ = session
            return OrderORM(
                id=order_id,
                user_id=1,
                amount=Decimal("10"),
                currency="USD",
                payment_system="handmade",
                payment_id=None,
                promocode_id=None,
                is_inited=False,
                is_executed=False,
                is_paid=False,
                is_cancelled=False,
                is_refunded=False,
                kind="order",
            )

    class FakeOrderSerializer:
        async def get_user_orders(self, session, user_id):
            _ = session
            _ = user_id
            return []

        async def serialize_order(self, session, order):
            _ = session
            return {
                "id": str(order.id),
                "user_id": order.user_id,
                "amount": float(order.amount),
                "currency": order.currency,
                "payment_system": order.payment_system,
                "payment_id": order.payment_id,
                "promocode_id": order.promocode_id,
                "is_inited": order.is_inited,
                "is_executed": order.is_executed,
                "is_paid": order.is_paid,
                "is_cancelled": order.is_cancelled,
                "is_refunded": order.is_refunded,
                "state": "created",
                "items": [],
                "payment": None,
            }

    class FakePaymentRuntime:
        async def get_order(self, session, order_id):
            return await FakeOrderRuntime().get_order(session, order_id)

        async def init_payment(self, session, order, payload, request_base_url):
            _ = session
            _ = order
            _ = payload
            _ = request_base_url
            return {
                "id": 1,
                "amount": 10.0,
                "currency": "USD",
                "kind": "handmade",
                "payment_url": None,
                "is_paid": False,
                "extras": None,
            }

    class FakeCommerceModule:
        def create_base_runtime(self):
            return FakeBaseRuntime()

        def create_product_serializer(self):
            return FakeProductSerializer()

        def create_order_runtime(self):
            return FakeOrderRuntime()

        def create_order_serializer(self):
            return FakeOrderSerializer()

        def create_payment_runtime(self):
            return FakePaymentRuntime()

    class FakeSession:
        async def commit(self) -> None:
            return None

    async def get_session():
        return FakeSession()

    def get_user():
        return SimpleNamespace(id=1, is_staff=False)

    app = FastAPI()
    app.include_router(
        create_router(
            CommerceHTTPConfig(
                get_db_session_dependency=get_session,
                get_current_user_dependency=get_user,
                get_commerce_module=FakeCommerceModule,
                build_actor=lambda user: CommerceUserActorDTO(id=user.id),
                get_user_id=lambda user: int(user.id),
                is_staff=lambda user: bool(user.is_staff),
            ),
        ),
        prefix="/api/v1",
    )

    client = TestClient(app)

    assert client.get("/api/v1/payment/types/").json() == {"USD": ["handmade"]}
    assert client.get("/api/v1/products/").json() == []
    assert client.get("/api/v1/user/balance/").json() == {"balance": 42.0}
