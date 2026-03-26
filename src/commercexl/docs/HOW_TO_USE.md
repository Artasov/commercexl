# HOW_TO_USE

## 1. Create `CommerceModule`

```python
from decimal import Decimal
from functools import lru_cache

from commercexl import (
    BalanceOrderItemService,
    BalancePaymentService,
    BalanceProductService,
    BaseConfig,
    CommerceModule,
    DefaultOrderItemService,
    HandMadePaymentService,
    OrderRuntimeConfigBuilder,
    PaymentConfigBuilder,
    ProductOrderConfig,
    ProductOrderConfigBuilder,
)
from my_app.services.commerce import (
    MyOrderItemService,
    MyProductService,
    MySimpleProductService,
)
from my_app.services.payments import MyPaymentService


@lru_cache(maxsize=1)
def calc_sol_min_top_up() -> Decimal:
    return Decimal("0.01")


@lru_cache(maxsize=1)
def calc_sol_credits(amount: Decimal) -> Decimal:
    return amount * Decimal("1500000")


class ProjectCommerceConfig(BaseConfig):
    PAYMENT_SYSTEMS = {
        "RUB": (
            HandMadePaymentService.payment_system,
            BalancePaymentService.payment_system,
        ),
        "USD": (
            HandMadePaymentService.payment_system,
            BalancePaymentService.payment_system,
        ),
        "SOL": ("solana",),
    }
    MIN_TOP_UP_AMOUNTS = {
        "RUB": Decimal("50"),
        "USD": Decimal("1"),
        "SOL": calc_sol_min_top_up,
    }
    CREDITS_CONVERTERS = {
        "RUB": Decimal("110"),
        "USD": Decimal("10000"),
        "SOL": calc_sol_credits,
    }
    MAX_TOP_UP_AMOUNT = Decimal("1000000")


commerce = CommerceModule(
    config_class=ProjectCommerceConfig,
    product_orders=ProductOrderConfigBuilder(
        ProductOrderConfig(BalanceProductService, BalanceOrderItemService),
        ProductOrderConfig(MyProductService, MyOrderItemService),
        ProductOrderConfig(MySimpleProductService, DefaultOrderItemService),
    ),
    order_runtime=OrderRuntimeConfigBuilder(),
    payments=PaymentConfigBuilder(
        HandMadePaymentService,
        BalancePaymentService,
        MyPaymentService,
    ),
)
```

Important:

- `config_class` is a class, not an instance.
- `PAYMENT_SYSTEMS` must contain at least one currency.
- `MIN_TOP_UP_AMOUNTS` accepts `Decimal` or `() -> Decimal`.
- `CREDITS_CONVERTERS` accepts `Decimal` or `(amount: Decimal) -> Decimal`.
- expensive converter functions should be cached.

## 2. Add a product

```python
from decimal import Decimal

from commercexl import (
    AbstractOrderItemService,
    AbstractProductService,
    DefaultOrderItemService,
    DefaultProductService,
)


class MyOrderItemService(AbstractOrderItemService):
    async def create_item_record(self, payload, amount) -> MyOrderItemORM:
        _ = amount
        return MyOrderItemORM(
            order_item_id=self.order_item.id,
            my_field=payload["my_field"],
        )

    async def calc_amount(self) -> Decimal:
        return Decimal("10")


class MyProductService(AbstractProductService[MyOrderItemORM]):
    kind = "my_product"
    product_kinds = ("myproduct",)
    item_kinds = ("myproductitem",)
    product_model = MyProductORM
    item_model = MyOrderItemORM
    default_order_item_service_class = MyOrderItemService


class MySimpleProductService(DefaultProductService[None]):
    kind = "my_simple_product"
    product_kinds = ("mysimpleproduct",)
    item_kinds = ("mysimpleproductitem",)
    item_model = None
    default_order_item_service_class = DefaultOrderItemService
```

Short version:

- `AbstractProductService` describes the product kind.
- `AbstractOrderItemService` describes one order item flow for that product.
- if a product has no extra item record, `item_model = None` is enough.

## 3. Add a payment service

```python
from commercexl import AbstractCallbackPaymentService, AbstractPaymentService, OrderDTO, PaymentORM


class MyPaymentService(AbstractPaymentService):
    payment_system = "my_payment"
    payment_kind = "mypayment"

    async def create(self, session, order, amount, request_base_url) -> PaymentORM: ...
    async def is_paid(self, session, payment_id) -> bool: ...


class MyCallbackPaymentService(AbstractCallbackPaymentService):
    payment_system = "my_payment"
    payment_kind = "mypayment"

    async def create(self, session, order, amount, request_base_url) -> PaymentORM: ...
    async def is_paid(self, session, payment_id) -> bool: ...
    async def confirm(self, session, data) -> OrderDTO: ...
    async def check(self, session, data) -> OrderDTO: ...
```

## 4. Use in FastAPI

```python
from fastapi import APIRouter

from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router


router = APIRouter()
router.include_router(
    create_router(
        CommerceHTTPConfig(
            get_db_session_dependency=get_db_session,
            get_current_user_dependency=get_current_user,
            get_commerce_module=lambda: commerce,
            build_actor=lambda user: CommerceUserActorDTO(id=user.id),
            get_user_id=lambda user: int(user.id),
            is_staff=lambda user: bool(user.is_staff),
        ),
    ),
)
```

Add project-specific extras next to this router, not inside `commercexl` itself.

## 5. Override `OrderRuntime` only if needed

```python
from decimal import Decimal

from commercexl import OrderDTO
from commercexl.services.order.order_runtime import OrderRuntime


class MyOrderRuntime(OrderRuntime):
    async def calc_order_amount(self, session, order) -> Decimal:
        return await super().calc_order_amount(session, order)

    async def init_existing_order(self, session, order, request_base_url, init_payment) -> OrderDTO:
        return await super().init_existing_order(session, order, request_base_url, init_payment)

    async def execute_order(self, session, order) -> None:
        await super().execute_order(session, order)

    async def cancel_order(self, session, order) -> None:
        await super().cancel_order(session, order)

    async def revoke_order(self, session, order) -> None:
        await super().revoke_order(session, order)
```
