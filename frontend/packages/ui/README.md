# @orcestr/commerce-ui

Provider-neutral React components for CommerceXL checkout surfaces. Payment providers remain
separate packages; this package owns the shared dialog shell and explicit payment-method choice.

```bash
npm install @orcestr/commerce-ui @orcestr/ui
```

Import `@orcestr/commerce-ui/styles.css` once in the application root. Use
`CommercePaymentMethodPicker` before creating an order and `CommerceCheckoutDialog` as the single
accessible modal shell around the selected provider UI.

The package never computes prices and never accepts a client-supplied amount. Render server-owned
catalog options and submit only their stable option IDs to checkout.

## Composing a provider

Use `CommercePaymentMethodPicker` for all available provider options and keep
`CommerceCheckoutDialog` as the single modal shell. Mount the selected provider view inside the
dialog instead of creating a separate modal per provider.

For Solana checkout, install the published provider packages:

```bash
npm install @orcestr/commerce-solana-core @orcestr/commerce-solana-react @orcestr/commerce-solana-ui @tanstack/react-query
```

Import `@orcestr/commerce-solana-ui/styles.css`, then render `SolanaCheckout` inside the shared
dialog with `showHeader={false}`. The Solana view automatically creates a fresh short-lived wallet
action and shows the QR code, deep link and payment states. Only authoritative backend `paid` state
may unlock a product; a wallet callback is not payment proof.

See the [CommerceXL integration guide](https://github.com/Artasov/commercexl/blob/master/src/commercexl/docs/HOW_TO_USE.md#6-compose-the-provider-neutral-checkout)
and [Orcestr Commerce Solana](https://github.com/Artasov/orcestr-commerce-solana) for the complete
backend, authentication, realtime and finalized-verification boundaries.

## Build and local integration

```bash
cd frontend
npm ci
npm run build
npm run pack:dry-run
```

For a local Orcestr consumer, point to `../commercexl/frontend/packages/ui` through the consumer's
local-library helper before starting its dev server. Do not use a global `npm link`.

Releases use `commerce-ui-vX.Y.Z` tags. After the first manual npm publish creates the package, the
`CI/CD` workflow publishes later tags with npm Trusted Publishing and provenance.
