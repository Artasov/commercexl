# Changelog

## Frontend UI 0.1.2

- Support Orcestr UI 0.8 and verify checkout against UI 0.8.3.
- Use the same OIDC-compatible npm version as the Solana release workflow.

## Frontend UI 0.1.1

- Move checkout dismissal to an accessible close icon beside the title.
- Respect the payment submission lock for every dismissal path, including Escape.

## 0.3.3

- Added the typed async `filter_public_products` host hook to `CommerceHTTPConfig`.
- Applied host product visibility filtering only to the public `GET /products/` catalog while
  preserving the previous full-catalog behavior by default.

## 0.3.2

- Added the authoritative order-snapshot `amount` and `currency` to `PaymentOptionDTO`.
- Documented host-defined commercial currencies and database-backed per-product prices.
- Added contract coverage for an arbitrary application-token currency and catalog-price snapshot
  preservation across payment option and payment-attempt creation.
