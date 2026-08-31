# Changelog

## 0.3.3

- Added the typed async `filter_public_products` host hook to `CommerceHTTPConfig`.
- Applied host product visibility filtering only to the public `GET /products/` catalog while
  preserving the previous full-catalog behavior by default.

## 0.3.2

- Added the authoritative order-snapshot `amount` and `currency` to `PaymentOptionDTO`.
- Documented host-defined commercial currencies and database-backed per-product prices.
- Added contract coverage for an arbitrary application-token currency and catalog-price snapshot
  preservation across payment option and payment-attempt creation.
