# CommerceXL integration guide (0.3)

## 1. Assemble `CommerceModule`

```python
from decimal import Decimal

from commercexl import (
    BalanceOrderItemService,
    BalancePaymentService,
    BalanceProductService,
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
    PAYMENT_SYSTEMS = {
        "RUB": ("handmade", "balance"),
        "USD": ("handmade", "balance"),
        "SOL": ("project_provider",),
    }
    MIN_TOP_UP_AMOUNTS = {
        "RUB": Decimal("50"),
        "USD": Decimal("1"),
        "SOL": Decimal("0.01"),
    }
    CREDITS_CONVERTERS = {
        "RUB": Decimal("110"),
        "USD": Decimal("10000"),
        "SOL": lambda amount: amount * Decimal("1500000"),
    }


commerce = CommerceModule(
    config_class=ProjectCommerceConfig,
    product_orders=ProductOrderConfigBuilder(
        ProductOrderConfig(BalanceProductService, BalanceOrderItemService),
        ProductOrderConfig(MyProductService, MyOrderItemService),
        ProductOrderConfig(MySimpleProductService, DefaultOrderItemService),
    ),
    payments=PaymentConfigBuilder(
        PaymentProviderRegistration("handmade", "handmade", HandMadePaymentService),
        PaymentProviderRegistration("balance", "balance", BalancePaymentService),
        PaymentProviderRegistration("project_provider", "gateway", create_gateway_service),
    ),
    order_access_policy=ProjectOrderAccessPolicy(),
    public_base_url="https://commerce.example.com",
)
```

`PAYMENT_SYSTEMS` is only a coarse allowlist by commercial currency. The provider's
`list_options(...)` method decides which concrete options are currently available for an actor and
order. Provider systems and identities are normalized and must be unique.

`public_base_url` is explicit trusted configuration. Do not derive it from `Host`, forwarded headers
or an incoming request URL.

## 2. Define product and order-item services

```python
from decimal import Decimal

from commercexl import AbstractOrderItemService, AbstractProductService, DefaultOrderItemService


class MyOrderItemService(AbstractOrderItemService):
    async def create_item_record(self, payload, amount) -> MyOrderItemORM:
        self.item_record = MyOrderItemORM(
            order_item_id=self.order_item.id,
            my_field=payload["my_field"],
        )
        return self.item_record

    async def calc_amount(self) -> Decimal:
        return Decimal("10")


class MyProductService(AbstractProductService[MyOrderItemORM]):
    kind = "my_product"
    product_kinds = ("myproduct",)
    item_kinds = ("myproductitem",)
    product_model = MyProductORM
    item_model = MyOrderItemORM
    default_order_item_service_class = MyOrderItemService


class MySimpleProductService(AbstractProductService[None]):
    kind = "my_simple_product"
    product_kinds = ("mysimpleproduct",)
    item_kinds = ("mysimpleproductitem",)
    item_model = None
    default_order_item_service_class = DefaultOrderItemService
```

Prices and balances use `Decimal` in Python and `Numeric(20, 6)` in the built-in models. Public JSON
uses decimal strings. A provider-specific raw blockchain amount belongs in its child model as an
integer/base-unit value, not in the CommerceXL commercial `currency` or `amount` fields.
`ProductPriceORM.currency` accepts any normalized host-defined code up to 12 characters. Add one
row per `(product_id, currency)`; do not put catalog prices in environment variables. Order and
order-item rows copy that selected price at creation time and remain unchanged when the catalog row
is edited later.

## 3. Implement a payment provider

```python
from commercexl import (
    AbstractCallbackPaymentService,
    PaymentCreateResult,
    PaymentOption,
    PaymentState,
    PaymentVerificationResult,
)


class GatewayPaymentService(AbstractCallbackPaymentService):
    def __init__(self, commerce, registration, gateway, clock) -> None:
        super().__init__(commerce, registration)
        self.gateway = gateway
        self.clock = clock

    async def list_options(self, session, order, actor):
        if not await self.gateway.is_available(session, order, actor):
            return ()
        return (
            PaymentOption(
                id="gateway:default",
                label="Gateway",
                action_kind="redirect",
            ),
        )

    async def create(self, session, context):
        intent = await self.gateway.create_intent(
            session=session,
            payment=context.payment,
            option=context.option,
            idempotency_key=context.idempotency_key,
        )
        session.add(GatewayPaymentORM(payment_ptr_id=context.payment.id, intent_id=intent.id))
        action = await self.gateway.issue_action(intent, context.public_base_url)
        return PaymentCreateResult(action=action)

    async def get_action(self, session, payment):
        intent = await self.gateway.get_intent(session, payment.id)
        return await self.gateway.issue_action(intent, self.commerce.commerce_module.public_base_url)

    async def cancel(self, session, payment):
        evidence = await self.gateway.cancel(payment.public_id)
        return PaymentVerificationResult(
            state=PaymentState.CANCELLED,
            reason_code=evidence.reason_code,
        )

    async def refund(self, session, payment):
        refund = await self.gateway.refund(payment.public_id)
        return PaymentVerificationResult(
            state=PaymentState.REFUND_PENDING,
            reason_code=refund.reason_code,
        )

    async def verify(self, session, payment, payload):
        evidence = await self.gateway.verify(payload)
        return PaymentVerificationResult(
            state=evidence.state,
            evidence_key=evidence.unique_key,
            reason_code=evidence.reason_code,
            evidence=evidence.safe_metadata,
        )


def create_gateway_service(commerce, registration):
    return GatewayPaymentService(
        commerce,
        registration,
        gateway=project_gateway,
        clock=project_clock,
    )
```

Rules for providers:

- create a child row referencing the canonical `PaymentORM`; do not create a parallel attempt;
- do not accept the final amount, currency, arbitrary provider system or asset identity from the
  client;
- do not mutate `OrderORM`, execute product effects or publish network events directly;
- return only typed checkout actions and verification results;
- keep callback verification deterministic and claim a globally unique `evidence_key` for observed,
  confirmed, paid and refunded results;
- persist only safe diagnostic evidence; never put bearer capabilities, credentials or raw secrets
  in `PaymentORM.verification_data`, logs or outbox payloads;
- issue redirect/transaction capability values from `get_action(...)`. Core persists only action
  kind and expiry.

Provider create/cancel/refund operations must be idempotent by canonical payment identity. A DB
exception rolls back CommerceXL state, but a remote provider side effect may already exist and must
be recoverable by the same idempotency key.

## 4. Wire authentication and HTTP

```python
from fastapi import APIRouter, Depends

from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router


async def commerce_actor(user=Depends(get_current_user)) -> CommerceUserActorDTO:
    return CommerceUserActorDTO(
        id=user.id,
        permissions=frozenset(await permission_service.for_user(user.id)),
    )


async def filter_public_products(session, products):
    hidden_kinds = await host_catalog.get_orchestrated_product_kinds(session)
    return [product for product in products if product.kind not in hidden_kinds]


router = APIRouter()
router.include_router(
    create_router(
        CommerceHTTPConfig(
            get_db_session_dependency=get_db_session,
            get_current_actor_dependency=commerce_actor,
            get_mutation_guard_dependency=check_csrf,
            get_commerce_module=lambda: commerce,
            prepare_order_payload=prepare_project_order_payload,
            filter_public_products=filter_public_products,
        ),
    ),
)
```

`get_current_actor_dependency` must reject anonymous requests wherever an actor is required.
`get_mutation_guard_dependency` is mandatory for every built-in mutation route. The default
`OwnerOrderAccessPolicy` hides foreign orders behind 404 and grants `commerce.manage` for management
operations; replace it with an injected policy when host permissions are more complex.

Host-orchestrated product kinds may require tenant links or purchase records. Reject those kinds in
`prepare_order_payload` and expose them only through host domain checkout endpoints; do not allow a
generic order endpoint to bypass their permission and linkage rules.

`filter_public_products` is an optional async visibility hook for `GET /products/`. It receives the
active `AsyncSession` and the already serialized `list[ProductDTO]`; returning a filtered list keeps
host-orchestrated products out of the generic catalog. The default `None` preserves the complete
catalog. The hook does not alter any internal serializer, product lookup or checkout authorization.

## 5. Use the two-phase checkout

Create a server-priced order:

```http
POST /orders/
Idempotency-Key: order-01J...
Content-Type: application/json

{"product": 42, "currency": "USD"}
```

Then list options and create one attempt:

```http
GET /orders/{order_id}/payment-options/

POST /orders/{order_id}/payment-attempts/
Idempotency-Key: payment-01J...
Content-Type: application/json

{"payment_option_id": "gateway:default"}
```

Every returned `PaymentOptionDTO` contains the `amount` and `currency` copied from the immutable
order snapshot. Providers return only `PaymentOption`; core adds snapshot and provider identity.

The create-attempt request has no amount, currency or free-form payment system. Repeating the same
idempotency key and fingerprint returns the same attempt; changing the payload produces `409`.

Read authoritative state through `GET /payments/{payment_public_id}/`. Use
`POST /payments/{payment_public_id}/checkout-action/` only when the UI needs a fresh action. Status
responses do not reproduce capability URLs from storage.

## 6. Compose the provider-neutral checkout

Install the shared shell once in the frontend application:

```bash
npm install @orcestr/commerce-ui @orcestr/ui react
```

For the published Solana provider, add the backend and frontend packages:

```bash
pip install orcestr-commerce-solana
npm install @orcestr/commerce-solana-core @orcestr/commerce-solana-react @orcestr/commerce-solana-ui @tanstack/react-query
```

Import all visual styles once at the application root:

```ts
import "@orcestr/ui/styles.css";
import "@orcestr/commerce-ui/styles.css";
import "@orcestr/commerce-solana-ui/styles.css";
```

Keep the UI boundary provider-neutral:

1. Render only the server-owned product price and `PaymentOptionDTO` values.
2. Use `CommercePaymentMethodPicker` for explicit provider selection.
3. Create the canonical payment attempt with only `payment_option_id` and an idempotency key.
4. Open one `CommerceCheckoutDialog` and mount the selected provider view inside it. When using
   `SolanaCheckout`, pass `showHeader={false}` so the shared dialog remains the only modal shell.
5. Let the Solana view issue its short-lived action automatically and display the QR code, deep
   link, waiting and result states. Do not persist or log the capability URI.
6. Invalidate the authoritative payment query from the host's shared realtime event source. Do not
   add a second WebSocket or polling loop.
7. Unlock the product only after the backend reports the canonical CommerceXL state as `paid`.

The host supplies its existing authenticated fetch, `QueryClient`, auth/CSRF behavior and shared
event source. The Solana packages do not create a parallel authentication session. See the
[Orcestr Commerce Solana documentation](https://github.com/Artasov/orcestr-commerce-solana) for
backend registration, Token-2022 allowlists, recipient policy, RPC settings, transaction requests
and reconciliation.

## 7. Apply trusted verification

Callback and reconciliation routes are provider/host responsibilities. After signature and payload
validation, load the provider child and canonical payment, call the provider verifier, then apply the
result through core in the same DB session:

```python
result = await provider.verify(session, payment, callback_payload)
payment_dto = await commerce.create_payment_runtime().apply_verification(
    session,
    payment.id,
    result,
)
await session.commit()
```

`apply_verification(...)` locks order then payment, claims evidence, performs the state transition,
executes or revokes product effects exactly once, and writes the outbox record atomically. It is a
trusted backend API and is intentionally not exposed as a generic public HTTP route.

## 8. Dispatch the transactional outbox

The host owns a worker that claims pending `PaymentOutboxEventORM` rows after commit, publishes a
minimal authenticated realtime invalidation event, and then marks each row delivered. Do not publish
Redis/WebSocket messages inside the payment transaction. Client event handlers must re-read the
authoritative REST state instead of trusting event payload as financial truth.

The canonical client payload contains `order_public_id`, `payment_public_id`, `revision` and `state`.
The outbox row keeps `user_id` separately as a server-side routing key.

## 9. Upgrade from 0.2

Do not keep both contracts. Remove the old payment URL, boolean order/payment flags, one-step order
creation and provider class registration in the same host release. Follow
[`MIGRATION_0_3.md`](./MIGRATION_0_3.md) for schema backfill order and endpoint mapping.
