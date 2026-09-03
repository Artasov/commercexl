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

CommerceXL provides reusable catalog, order, balance and payment primitives for FastAPI,
Pydantic 2 and SQLAlchemy 2 applications. The host application owns the database engine,
sessions, users, authentication, CSRF policy, migrations and provider-specific callback routes.

## Status

| Item | Value |
| --- | --- |
| Package | `commercexl` |
| Version | `0.3.3` |
| Status | Beta, breaking from 0.2 |
| Runtime | Python 3.12+ |
| Frameworks | FastAPI, SQLAlchemy 2, Pydantic 2 |

## What Is Included

| Area | Includes |
| --- | --- |
| Catalog | products, exact decimal prices and extensible product services |
| Orders | multi-item orders with canonical order and item states |
| Payments | canonical payment attempts, strict provider registry and typed checkout actions |
| Lifecycle | idempotent create, verification, cancellation, refund and exact-once product finalization |
| Balances | internal credit balances and currency conversion settings |
| Promotions | promocodes and gift-certificate foundations |
| Events | transactional payment outbox and globally unique provider evidence claims |
| HTTP | auth-neutral FastAPI router assembled through `create_router(...)` |
| Persistence | typed SQLAlchemy models exposed through `CommerceBase` |

CommerceXL does not include wallet integration, a blockchain verifier or payment-provider
credentials. Those belong in separate provider packages and host adapters. The provider-neutral
React checkout primitives are published separately as `@orcestr/commerce-ui` from the
`frontend/packages/ui` workspace.

## Checkout UI and Solana payments

The public packages compose without merging provider logic into the commerce core:

| Package | Responsibility |
| --- | --- |
| [`commercexl`](https://pypi.org/project/commercexl/) | Authoritative products, database-backed prices, orders, payment attempts, verification lifecycle and exactly-once fulfillment. |
| [`@orcestr/commerce-ui`](https://www.npmjs.com/package/@orcestr/commerce-ui) | Provider-neutral React dialog and standardized payment-method selection. |
| [`orcestr-commerce-solana`](https://pypi.org/project/orcestr-commerce-solana/) | Backend Solana provider, transaction requests, reconciliation and finalized transaction verification. |
| [`@orcestr/commerce-solana-core`](https://www.npmjs.com/package/@orcestr/commerce-solana-core) | Typed API client, exact amounts, Solana URI helpers and client-side transaction validation. |
| [`@orcestr/commerce-solana-react`](https://www.npmjs.com/package/@orcestr/commerce-solana-react) | React Query, Wallet Standard and shared realtime-event integration. |
| [`@orcestr/commerce-solana-ui`](https://www.npmjs.com/package/@orcestr/commerce-solana-ui) | QR, wallet deep link, waiting, confirmation and recovery views built on `@orcestr/ui`. |

The host renders server-owned prices and payment options in one Commerce dialog, then mounts the
selected provider UI inside it. The Solana add-on automatically issues a short-lived wallet action
and displays its QR code and deep link. A wallet callback is never proof of payment: only the
backend's exact `finalized` verification may advance CommerceXL to `paid` and fulfill the order.

The Solana provider supports native SOL and explicitly allowlisted Token-2022 fungible assets. It
deliberately rejects the legacy SPL Token Program. Verification works through standard Solana
JSON-RPC and does not require a paid API, webhook, indexer, hosted checkout or a server-side wallet
private key. Authentication, ownership and CSRF remain injected host responsibilities, including
when the host uses Orcestr Auth.

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
    PaymentProviderRegistration,
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
    payments=PaymentConfigBuilder(
        PaymentProviderRegistration(
            system="handmade",
            provider_kind="handmade",
            factory=HandMadePaymentService,
        ),
    ),
    public_base_url="https://commerce.example.com",
)
```

Provider registration is strict. A duplicate normalized `system`, a missing provider referenced by
`PAYMENT_SYSTEMS`, or a factory returning the wrong service type fails during module construction.

## FastAPI Integration

The host supplies an authenticated actor dependency and a mandatory mutation guard. For
cookie-authenticated applications, the mutation guard is the host CSRF dependency.

```python
from fastapi import Depends
from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router


async def get_commerce_actor(user=Depends(get_current_user)) -> CommerceUserActorDTO:
    return CommerceUserActorDTO(id=user.id, permissions=frozenset(user.permissions))


app.include_router(
    create_router(
        CommerceHTTPConfig(
            get_db_session_dependency=get_db_session,
            get_current_actor_dependency=get_commerce_actor,
            get_mutation_guard_dependency=check_csrf,
            get_commerce_module=lambda: commerce,
        ),
    ),
    prefix="/api/v1",
)
```

The optional `filter_public_products` hook receives the active `AsyncSession` and the already
serialized `list[ProductDTO]`. It applies only to `GET /products/`, allowing a host to keep
tenant-bound or otherwise host-orchestrated products out of the generic public catalog without
changing CommerceXL product storage:

```python
async def filter_public_products(session, products):
    hidden_kinds = await host_catalog.get_orchestrated_product_kinds(session)
    return [product for product in products if product.kind not in hidden_kinds]


CommerceHTTPConfig(
    # ...required dependencies...
    filter_public_products=filter_public_products,
)
```

With the default `None`, the endpoint returns the full serialized CommerceXL catalog as before.
The hook does not affect internal serializers, balance-product lookup, gift certificates or order
creation; hosts must still enforce checkout authorization independently.

The checkout is intentionally two-phase:

1. `POST /orders/` creates a server-priced order and requires `Idempotency-Key`.
2. `GET /orders/{order_id}/payment-options/` returns options available to that actor and order.
3. `POST /orders/{order_id}/payment-attempts/` accepts only `payment_option_id` and another
   `Idempotency-Key`.
4. `GET /payments/{payment_public_id}/` returns authoritative state without issuing a secret.
5. `POST /payments/{payment_public_id}/checkout-action/` issues a fresh provider action.

Amounts are `Decimal` in Python and decimal strings in JSON. The client cannot submit the final
payment amount, commercial currency or arbitrary provider system when creating an attempt.
Each `PaymentOptionDTO` repeats the authoritative order-snapshot `amount` and `currency`, so a
catalog price change after order creation cannot change the amount shown or paid for that order.
Currency codes are host-defined strings (for example, fiat or application tokens), not a closed
CommerceXL enum.

## Provider Contract

Provider packages implement `AbstractPaymentService` or `AbstractCallbackPaymentService` and are
registered through `PaymentProviderRegistration`. The stable provider-facing imports include
`PaymentCreateContext`, `PaymentCreateResult`, `PaymentOption`, `CheckoutAction`,
`PaymentVerificationResult` and `PaymentState`.

The canonical `PaymentORM` is the extension root for provider child tables. Providers do not mutate
orders or mark them paid directly. A trusted callback/reconciliation adapter returns a typed
verification result and passes it to `PaymentRuntime.apply_verification(...)` in the current DB
session.

Checkout capability URLs and transaction-request bearer values must be issued by
`get_action(...)`; CommerceXL persists only non-secret action metadata. Safe provider evidence is
claimed globally and payment changes write `PaymentOutboxEventORM` in the same transaction.

## Database Migrations

CommerceXL does not ship application migrations. Add its metadata to the host Alembic setup and
generate/review migrations in the host repository:

```python
from commercexl import CommerceBase
from my_project.db import Base

target_metadata = [Base.metadata, CommerceBase.metadata]
```

Version 0.3 is a deliberate breaking schema/API release. Follow the
[0.2 to 0.3 migration guide](./src/commercexl/docs/MIGRATION_0_3.md) before upgrading production
data.

## Documentation

- [Integration guide](./src/commercexl/docs/HOW_TO_USE.md)
- [Checkout UI and Solana composition](./src/commercexl/docs/HOW_TO_USE.md#6-compose-the-provider-neutral-checkout)
- [0.3 migration guide](./src/commercexl/docs/MIGRATION_0_3.md)
- [Promocodes](./src/commercexl/docs/PROMOCODES.md)
- [Gift certificates](./src/commercexl/docs/GIFT_CERTIFICATES.md)
- [Release guide](./RELEASE_GUIDE.md)

## Development

```bash
uv sync --all-extras
uv run pytest -q
uv build
```

## License

Licensed under the [Mozilla Public License 2.0](./LICENSE). Commercial use is permitted; changes
to MPL-covered files remain subject to the MPL. See [NOTICE](./NOTICE) and
[TRADEMARKS.md](./TRADEMARKS.md).

## Orcestr Ecosystem

- [Orcestr](https://orcestr.com)
- [Orcestr Auth](https://github.com/Artasov/orcestr-auth)
- [Orcestr UI](https://github.com/Artasov/orcestr-ui)
- [Orcestr Commerce Solana](https://github.com/Artasov/orcestr-commerce-solana)
- [Orcestr OS](https://github.com/Artasov/orcestr-os)
