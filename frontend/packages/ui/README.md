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
