# commercexl

`commercexl` is a reusable commerce core for:

- product catalog records
- checkout orders
- order items
- payment systems
- FastAPI router assembly

It does not create your DB engine, session factory, auth, or project-specific payment callbacks.

## Installation

```bash
pip install commercexl
```

For tests and local development:

```bash
pip install "commercexl[test]"
pip install "commercexl[dev]"
```

## What the library gives you

- SQLAlchemy models via `CommerceBase`
- explicit module wiring via `CommerceModule`
- abstract services for products, order items, and payments
- built-in balance and handmade payments
- FastAPI router factory via `create_router(...)`

## Quick start

```python
from decimal import Decimal

from commercexl import (
    BaseConfig,
    CommerceModule,
    DefaultOrderItemService,
    HandMadePaymentService,
    PaymentConfigBuilder,
    ProductOrderConfig,
    ProductOrderConfigBuilder,
)


class ProjectCommerceConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("10000")}


commerce = CommerceModule(
    config_class=ProjectCommerceConfig,
    product_orders=ProductOrderConfigBuilder(
        ProductOrderConfig(MyProductService, DefaultOrderItemService),
    ),
    payments=PaymentConfigBuilder(HandMadePaymentService),
)
```

## FastAPI integration

```python
from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router

app.include_router(
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
    prefix="/api/v1",
)
```

## Alembic

`commercexl` does not ship migrations. The host project owns migrations.

Add library metadata to your Alembic `target_metadata`:

```python
from commercexl import CommerceBase
from my_project.db import Base

target_metadata = [
    Base.metadata,
    CommerceBase.metadata,
]
```

## Docs

- [How to use](./src/commercexl/docs/HOW_TO_USE.md)
- [Promocodes](./src/commercexl/docs/PROMOCODES.md)

## Testing

```bash
pytest
```
