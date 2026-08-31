# Migrating CommerceXL 0.2 to 0.3

CommerceXL 0.3 is an intentional breaking beta release. It replaces the one-step checkout and
boolean lifecycle with a canonical, auditable payment-attempt model. There is no legacy adapter or
fallback serialization.

## Required deployment order

1. Stop payment writers and background callback/reconciliation workers.
2. Back up the host database and verify restoration.
3. Deploy the host migration while no 0.2 process can write commerce tables.
4. Deploy CommerceXL 0.3 and migrated provider adapters together.
5. Run data invariants before re-enabling checkout and callbacks.
6. Start the outbox dispatcher, then resume payment workers and HTTP traffic.

CommerceXL exposes metadata but does not ship a host migration. Generate and review the migration
in the application repository because only the host knows existing provider tables and historical
data semantics.

## Schema changes

### Orders and order items

`commerce_order` now stores one canonical `state` instead of payment fields and lifecycle booleans.
Remove `payment_id`, `payment_system`, `is_inited`, `is_executed`, `is_paid`, `is_cancelled` and
`is_refunded` after backfill. Add:

- `idempotency_key` and `idempotency_fingerprint`;
- `state` with values `created`, `ready_for_payment`, `executed`, `cancelled`, `refunded`;
- exact `amount NUMERIC(20, 6)` and a currency code up to 12 characters.

`commerce_orderitem` similarly replaces lifecycle booleans with `state`: `created`, `ready`,
`executed`, `cancelled` or `refunded`. Its amount becomes `NUMERIC(20, 6)`.

When mapping valid 0.2 rows, use a single explicit priority suitable for host data, normally
`refunded` → `cancelled` → `executed/paid` → `ready` → `created`. Abort the migration if a row has an
impossible combination that cannot be resolved from provider evidence. Do not preserve contradictory
booleans as hidden compatibility columns.

Historical orders did not have an idempotency request. Backfill a deterministic unique migration
value and its SHA-256 fingerprint; new requests must use the actual user-scoped key.

### Canonical payment attempts

The existing `commerce_payment` table remains the extension root. Do not add a parallel payment
attempt table. Add/backfill:

- `public_id`, `order_id`, `attempt_no` and `active_slot`;
- `user_id`, `payment_system`, immutable provider `kind` and `payment_option_id`;
- exact commercial `amount/currency` snapshot;
- canonical `state`, `reason_code`, safe `verification_data` and monotonic `revision`;
- idempotency key/fingerprint;
- expiry, paid, cancelled, failed, refunded, created and updated timestamps.

Required uniqueness:

- `(order_id, attempt_no)`;
- `(user_id, idempotency_key)`;
- `(order_id, active_slot)`, where terminal rows use `NULL`.

In 0.3, `active_slot = 1` for `created`, `requires_action`, `processing`, `observed`, `confirmed`,
`paid`, `review` and `refund_pending`. It is `NULL` only for `expired`, `cancelled`, `failed` and
`refunded`. `paid` remains lifecycle-active because it may enter a refund process; an executed order
still rejects new checkout attempts.

Link each historical payment to exactly one order before making `order_id` non-null. If historical
data violates this relation, move it to an audited reconciliation queue instead of guessing. Keep
provider child primary keys pointing to the same canonical `commerce_payment.id` and add cascading
foreign keys where appropriate.

Do not add persisted checkout URLs or capability payloads. Provider child tables may store a safe
intent snapshot and capability digest, while raw bearer values are issued on demand.

### Evidence and outbox

Create:

- `commerce_payment_evidence`, unique by `(payment_system, evidence_key)`;
- `commerce_payment_outbox`, unique by `(payment_id, revision, event_type)`.

The evidence table prevents one provider transaction/receipt from paying multiple attempts. The
outbox dispatcher publishes only committed rows and marks delivery separately. Do not backfill fake
events for historical rows unless consumers explicitly need them; if you do, allocate deterministic
revisions without colliding with live events.

### Exact money

Built-in price, order, payment, discount and balance columns use `NUMERIC(20, 6)`. Audit existing
values before altering types. Reject values that need more than six fractional digits or exceed 14
integer digits; never round silently during migration. Public JSON values are strings such as
`"15.125"`, not JSON numbers.

## Provider API changes

Replace service classes passed directly to `PaymentConfigBuilder` with explicit registrations:

```python
PaymentConfigBuilder(
    PaymentProviderRegistration("gateway", "gateway", create_gateway_service),
)
```

Every provider implements:

- `list_options(session, order, actor)`;
- `create(session, PaymentCreateContext) -> PaymentCreateResult`;
- `get_action(session, payment) -> CheckoutAction`;
- `cancel(session, payment) -> PaymentVerificationResult`;
- optional `refund(...)`; callback providers also implement `verify(...)`.

Remove provider code that edits orders, executes products, publishes realtime messages, trusts a
client amount/currency/system or persists a checkout capability. Pass verified results to
`PaymentRuntime.apply_verification(...)`.

## HTTP mapping

| Removed 0.2 contract | 0.3 replacement |
| --- | --- |
| `POST /orders/create/` with payment selection | `POST /orders/`, then explicit payment attempt |
| `GET /payment/types/` | order-scoped `GET /orders/{id}/payment-options/` |
| `POST /orders/{id}/init-payment/` | authenticated `POST /orders/{id}/payment-attempts/` |
| stored/returned `payment_url` | typed action from create or checkout-action issuance |
| admin execute/init/delete routes | trusted runtime methods behind host-owned authorization |
| boolean response flags | `OrderState`, `OrderItemState`, `PaymentState` |

Both create mutations require `Idempotency-Key`. The payment-attempt body contains only
`payment_option_id`. Configure `CommerceHTTPConfig` with an authenticated actor dependency and a
mandatory mutation/CSRF guard.

Before enabling the generic `/orders/` route, use `prepare_order_payload` and product service policy
to reject host-orchestrated product kinds that require a tenant subscription, purchase link or other
domain record. Keep those products behind host-owned checkout endpoints with their tenant permission
checks; a generic CommerceXL order must not bypass required domain linkage.

## Validation after migration

Before opening traffic, verify:

- every payment has one valid order, unique attempt number and matching commercial quote;
- each order has at most one non-null active slot;
- no terminal payment holds an active slot and every non-terminal payment does;
- executed paid orders reference a canonical paid/refund lifecycle; cancelled/refunded orders are
  internally consistent;
- no duplicate provider evidence exists;
- all money values fit the new precision without implicit rounding;
- old routes and DTO fields are absent from OpenAPI and host code;
- callback replay does not execute a product effect twice;
- outbox rows are committed atomically and the dispatcher can retry without duplicate client state.

After publishing `0.3.0`, provider add-ons should use `commercexl>=0.3,<0.4`. Do not commit a lockfile
that resolves a local editable checkout as if it were the published artifact.
