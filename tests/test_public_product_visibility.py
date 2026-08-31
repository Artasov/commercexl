from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from commercexl import CommerceHTTPConfig, create_router
from commercexl.dto import ProductDTO, ProductPriceDTO


class FakeProductSerializer:
    def __init__(self, products: list[ProductDTO]) -> None:
        self.products = products

    async def list_products(self, session) -> list[ProductDTO]:
        _ = session
        return self.products


class FakeCommerceModule:
    def __init__(self, products: list[ProductDTO]) -> None:
        self.serializer = FakeProductSerializer(products)

    def create_product_serializer(self) -> FakeProductSerializer:
        return self.serializer


class FakeSession:
    pass


class PublicProductTestApp:
    def __init__(self, filter_public_products=None) -> None:
        self.session = FakeSession()
        self.products = [
            self.product(1, "Public plan", "balance"),
            self.product(2, "Host plan", "host_subscription"),
        ]
        self.commerce = FakeCommerceModule(self.products)

        async def get_session():
            return self.session

        app = FastAPI()
        app.include_router(
            create_router(
                CommerceHTTPConfig(
                    get_db_session_dependency=get_session,
                    get_current_actor_dependency=lambda: None,
                    get_mutation_guard_dependency=lambda: None,
                    get_commerce_module=lambda: self.commerce,
                    filter_public_products=filter_public_products,
                ),
            ),
        )
        self.client = TestClient(app)

    @staticmethod
    def product(product_id: int, name: str, kind: str) -> ProductDTO:
        return ProductDTO(
            id=product_id,
            name=name,
            is_available=True,
            is_installment_available=False,
            kind=kind,
            prices=[
                ProductPriceDTO(
                    id=product_id,
                    product=product_id,
                    currency="USD",
                    amount=Decimal("10"),
                ),
            ],
        )


def test_public_product_filter_receives_session_and_serialized_products():
    received: list[tuple[object, list[ProductDTO]]] = []

    async def filter_public_products(session, products):
        received.append((session, products))
        return products

    test_app = PublicProductTestApp(filter_public_products)

    response = test_app.client.get("/products/")

    assert response.status_code == 200
    assert received == [(test_app.session, test_app.products)]


def test_public_product_filter_can_hide_host_orchestrated_products():
    async def filter_public_products(session, products):
        _ = session
        return [product for product in products if product.kind != "host_subscription"]

    response = PublicProductTestApp(filter_public_products).client.get("/products/")

    assert response.status_code == 200
    assert [product["id"] for product in response.json()] == [1]


def test_public_product_filter_default_preserves_catalog():
    response = PublicProductTestApp().client.get("/products/")

    assert response.status_code == 200
    assert [product["id"] for product in response.json()] == [1, 2]
