from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from commercexl import (
    BalanceOrderItemService,
    BaseConfig,
    CommerceHTTPConfig,
    CommerceModule,
    CommerceUserActorDTO,
    HandMadePaymentService,
    PaymentConfigBuilder,
    PaymentProviderRegistration,
    create_router,
    get_default_commerce_module,
)


class TestConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("100")}


def handmade_registration() -> PaymentProviderRegistration:
    return PaymentProviderRegistration("handmade", "handmade", HandMadePaymentService)


def test_default_commerce_module_registers_balance_order_item_service():
    commerce = get_default_commerce_module()
    handler = commerce.create_base_runtime().product_registry.get_handler_by_kind("balance")

    assert handler is not None
    assert handler.get_order_item_service_class() is BalanceOrderItemService


def test_commerce_module_rejects_unregistered_configured_payment_system():
    class BrokenConfig(BaseConfig):
        PAYMENT_SYSTEMS = {"USD": ("handmade", "missing")}
        MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
        CREDITS_CONVERTERS = {"USD": Decimal("100")}

    with pytest.raises(TypeError, match="missing"):
        CommerceModule(
            config_class=BrokenConfig,
            payments=PaymentConfigBuilder(handmade_registration()),
        )


def test_commerce_module_rejects_request_derived_public_base_url_shape():
    with pytest.raises(TypeError, match="absolute HTTP origin"):
        CommerceModule(
            config_class=TestConfig,
            payments=PaymentConfigBuilder(handmade_registration()),
            public_base_url="https://commerce.example.com/untrusted/request/path",
        )


def test_payment_registration_is_normalized_strict_and_factory_injected():
    runtime = SimpleNamespace()
    registration = PaymentProviderRegistration(" HandMade ", " BuiltIn ", HandMadePaymentService)
    service = registration.create_service(runtime)

    assert registration.system == "handmade"
    assert registration.provider_kind == "builtin"
    assert service.commerce is runtime
    assert service.registration is registration

    with pytest.raises(TypeError, match="already registered"):
        PaymentConfigBuilder(registration).add(
            PaymentProviderRegistration("HANDMADE", "another-kind", HandMadePaymentService),
        )


def test_http_router_exposes_two_phase_checkout_without_legacy_routes():
    class FakeBaseRuntime:
        async def get_balance(self, session, user_id):
            _ = session
            _ = user_id
            return SimpleNamespace(amount=Decimal("42"))

    class FakeProductSerializer:
        async def get_latest_balance_product(self, session):
            _ = session
            return None

        async def list_products(self, session):
            _ = session
            return []

    class FakeCommerceModule:
        def create_base_runtime(self):
            return FakeBaseRuntime()

        def create_product_serializer(self):
            return FakeProductSerializer()

    class FakeSession:
        async def commit(self) -> None:
            return None

    async def get_session():
        return FakeSession()

    def get_actor() -> CommerceUserActorDTO:
        return CommerceUserActorDTO(id=1)

    def mutation_guard() -> None:
        return None

    app = FastAPI()
    app.include_router(
        create_router(
            CommerceHTTPConfig(
                get_db_session_dependency=get_session,
                get_current_actor_dependency=get_actor,
                get_mutation_guard_dependency=mutation_guard,
                get_commerce_module=FakeCommerceModule,
            ),
        ),
        prefix="/api/v1",
    )
    client = TestClient(app)

    assert client.get("/api/v1/products/").json() == []
    assert client.get("/api/v1/user/balance/").json() == {"balance": "42"}
    assert client.get("/api/v1/payment/types/").status_code == 404
    assert client.post(f"/api/v1/orders/{uuid4()}/init-payment/", json={}).status_code == 404

    paths = app.openapi()["paths"]
    assert "/api/v1/orders/{order_id}/payment-options/" in paths
    assert "/api/v1/orders/{order_id}/payment-attempts/" in paths
    assert "/api/v1/payments/{payment_public_id}/checkout-action/" in paths


def test_http_mutation_requires_authenticated_actor_and_host_guard():
    class FakeCommerceModule:
        pass

    async def get_session():
        return SimpleNamespace()

    def reject_actor():
        raise HTTPException(status_code=401, detail="Authentication required.")

    def actor() -> CommerceUserActorDTO:
        return CommerceUserActorDTO(id=1)

    def reject_mutation():
        raise HTTPException(status_code=403, detail="Mutation guard rejected request.")

    def allow_mutation() -> None:
        return None

    def build_client(actor_dependency, guard_dependency) -> TestClient:
        app = FastAPI()
        app.include_router(
            create_router(
                CommerceHTTPConfig(
                    get_db_session_dependency=get_session,
                    get_current_actor_dependency=actor_dependency,
                    get_mutation_guard_dependency=guard_dependency,
                    get_commerce_module=FakeCommerceModule,
                ),
            ),
        )
        return TestClient(app)

    request = {"product": 1, "currency": "USD"}
    headers = {"Idempotency-Key": "order-key"}
    assert build_client(reject_actor, allow_mutation).post("/orders/", json=request, headers=headers).status_code == 401
    assert build_client(actor, reject_mutation).post("/orders/", json=request, headers=headers).status_code == 403


def test_http_router_factory_supports_gift_certificate_routes(monkeypatch: pytest.MonkeyPatch):
    class FakeGiftCertificateService:
        def __init__(self, commerce_module) -> None:
            _ = commerce_module

        async def list(self, session):
            _ = session
            return [{
                "id": 10,
                "name": "Gift 100",
                "pic": None,
                "description": "Gift",
                "short_description": "Gift",
                "is_available": True,
                "is_installment_available": False,
                "kind": "gift_certificate",
                "prices": [],
                "product": {
                    "id": 1,
                    "name": "Target",
                    "pic": None,
                    "description": "Target",
                    "short_description": "Target",
                    "is_available": True,
                    "is_installment_available": False,
                    "kind": "software",
                    "prices": [],
                },
            }]

        async def get(self, session, product_id):
            _ = session
            return {
                "id": product_id,
                "name": "Gift 100",
                "pic": None,
                "description": "Gift",
                "short_description": "Gift",
                "is_available": True,
                "is_installment_available": False,
                "kind": "gift_certificate",
                "prices": [],
                "product": {
                    "id": 1,
                    "name": "Target",
                    "pic": None,
                    "description": "Target",
                    "short_description": "Target",
                    "is_available": True,
                    "is_installment_available": False,
                    "kind": "software",
                    "prices": [],
                },
            }

        async def activate(self, session, user_id, key):
            _ = session
            _ = user_id
            _ = key

    class FakeCommerceModule:
        pass

    class FakeSession:
        async def commit(self) -> None:
            return None

    async def get_session():
        return FakeSession()

    def get_actor() -> CommerceUserActorDTO:
        return CommerceUserActorDTO(id=7)

    def mutation_guard() -> None:
        return None

    monkeypatch.setattr("commercexl.http.GiftCertificate", FakeGiftCertificateService)

    app = FastAPI()
    app.include_router(
        create_router(
            CommerceHTTPConfig(
                get_db_session_dependency=get_session,
                get_current_actor_dependency=get_actor,
                get_mutation_guard_dependency=mutation_guard,
                get_commerce_module=FakeCommerceModule,
            ),
        ),
        prefix="/api/v1",
    )
    client = TestClient(app)

    list_response = client.get("/api/v1/gift-certificates/")
    detail_response = client.get("/api/v1/gift-certificates/10/")
    activate_response = client.post("/api/v1/gift-certificate/activate/", json={"key": str(uuid4())})

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert activate_response.status_code == 201
    assert activate_response.json() == {"detail": "Activated."}
