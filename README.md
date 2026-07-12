<p align="right">
  <strong>English</strong> · <a href="./README.ru.md">Русский</a>
</p>

<p align="center">
  <a href="https://orcestr.com">
    <img src="./assets/orcestr-banner.webp" alt="CommerceXL banner" width="100%" />
  </a>
</p>

# CommerceXL

[![PyPI](https://img.shields.io/pypi/v/commercexl)](https://pypi.org/project/commercexl/)
[![CI](https://github.com/Artasov/commercexl/actions/workflows/ci.yml/badge.svg)](https://github.com/Artasov/commercexl/actions/workflows/ci.yml)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](./LICENSE)

Composable commerce backend foundation for the [Orcestr](https://orcestr.com) ecosystem.

CommerceXL provides reusable product, order-item, payment and balance primitives for FastAPI and
SQLAlchemy applications. The host application keeps control of its database engine, sessions,
users, authentication, migrations and project-specific payment callbacks.

## Status

| Item | Value |
| --- | --- |
| Package | `commercexl` |
| Version | `0.2.0` |
| Status | Beta |
| Runtime | Python 3.12+ |
| Frameworks | FastAPI, SQLAlchemy 2, Pydantic 2 |

The public API is usable in Orcestr applications and remains subject to beta-level refinement
before the first stable major release.

## What Is Included

| Area | Includes |
| --- | --- |
| Catalog | reusable product contracts and service boundaries |
| Checkout | order and order-item DTOs and services |
| Payments | configurable payment providers and handmade payments |
| Balances | user credit balances and currency conversion settings |
| Promotions | promocode and gift-certificate foundations |
| HTTP | explicit FastAPI router assembly through `create_router(...)` |
| Persistence | typed SQLAlchemy models through `CommerceBase` |

## Installation

```bash
pip install commercexl
```

Optional development dependencies:

```bash
pip install "commercexl[test]"
pip install "commercexl[dev]"
```

## Quick Start

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

## FastAPI Integration

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

## Database Migrations

CommerceXL does not ship application migrations. Add its metadata to the host project's Alembic
configuration and create migrations in the host repository:

```python
from commercexl import CommerceBase
from my_project.db import Base

target_metadata = [Base.metadata, CommerceBase.metadata]
```

## Documentation

- [Integration guide](./src/commercexl/docs/HOW_TO_USE.md)
- [Promocodes](./src/commercexl/docs/PROMOCODES.md)
- [Gift certificates](./src/commercexl/docs/GIFT_CERTIFICATES.md)
- [Release guide](./RELEASE_GUIDE.md)

## Development

```bash
uv sync --all-extras
uv run pytest -q
uv build
```

PyCharm run configurations for dependency installation, tests, builds and releases live in
[`.run`](./.run).

## License

Licensed under the [Mozilla Public License 2.0](./LICENSE). Commercial use is permitted; changes
to MPL-covered files remain subject to the MPL. See [NOTICE](./NOTICE) and
[TRADEMARKS.md](./TRADEMARKS.md).

## Orcestr Ecosystem

- [Orcestr](https://orcestr.com)
- [Orcestr Auth](https://github.com/Artasov/orcestr-auth)
- [Orcestr UI](https://github.com/Artasov/orcestr-ui)
- [Orcestr Overview](https://github.com/Artasov/orcestr-overview)
