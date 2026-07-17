# SecuredMe commerce and identity research brief

Date: 2026-07-16  
Decision: PayPal for Web commerce; Square only for physical Tap to Pay; Escrow.com for project milestones; Google/GitHub/PayPal behind a SecuredMe OIDC broker.

## Evidence map

| Area | Primary evidence | Implementation conclusion |
| --- | --- | --- |
| PayPal Checkout | [Orders v2](https://developer.paypal.com/docs/api/orders/v2/), [JavaScript SDK](https://developer.paypal.com/sdk/js/) | Create orders server-side, redirect only to provider approval, and use request idempotency. |
| PayPal events | [Webhook verification](https://developer.paypal.com/api/rest/webhooks/rest/) | Verify transmissions through PayPal before changing a receipt or entitlement. |
| Recurring support | [Subscriptions](https://developer.paypal.com/docs/subscriptions/) | Use three pre-created CAD plans; custom monthly amounts are rejected. |
| PayPal mobile acceptance | [Payment links](https://www.paypal.com/ca/business/accept-payments/payment-links), [QR payments](https://www.paypal.com/ca/business/accept-payments/qr-code) | PayPal covers links, invoices, and QR; it is the online rail. |
| Square physical acceptance | [Tap to Pay Canada](https://squareup.com/ca/en/payments/tap-to-pay), [Square pricing](https://squareup.com/ca/en/pricing) | Square POS accepts contactless cards and wallets on compatible phones; no duplicate Web checkout. |
| Square events | [Webhook signature validation](https://developer.squareup.com/docs/webhooks/step3validate) | Validate `x-square-hmacsha256-signature` over notification URL plus raw body and reject replays. |
| OIDC security | [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html), [OAuth PKCE RFC 7636](https://www.rfc-editor.org/rfc/rfc7636) | Exact callback allowlist, one-time codes, PKCE S256, short ES256 tokens, public JWKS. |
| Escrow milestones | [Escrow.com milestone transactions](https://www.escrow.com/milestone-escrow) | Buyer funds 100%; each 50% release remains buyer-approved and human-controlled. |
| Canadian regulatory boundary | [FINTRAC money services businesses](https://fintrac-canafe.canada.ca/msb-esm/intro-eng) | SecuredMe does not custody fiat or virtual currency and does not create an internal escrow bot. |

## Repository evidence

- The canonical inventory contains twelve Education repositories and assigns `fnpqnn_gateway_MVP` as auth-enforcer owner.
- The previous 24-surface suite audit passed before implementation.
- Scholarium already had separate Google, GitHub, PayPal, and ChatGPT-context sessions; the new broker preserves separation and adds explicit linking rather than merging by email.
- Root Web styling already defines night/day, high contrast, reduced motion, and three neurodivergent reading profiles; the payment widget reuses those tokens.

## Confidence labels

- **Verified implementation:** receipt idempotency, Square HMAC verification, PayPal verification adapter, intake score, Escrow 50/50 calculation, OIDC PKCE exchange, ES256 JWKS, explicit linking, branded widget.
- **Verified external configuration:** dedicated PayPal Live app created with subscriptions, payment links, JS SDK v6, Login with PayPal, and a 15-event webhook.
- **Pending operator evidence:** correct-address PayPal Sandbox app, Square Business/Tap to Pay activation, live provider secrets, production service deployment, physical phone transaction/refund, Escrow.com API credentials.
- **cPanel mismatch:** the July 1 PDF confirms `paypal.securedme.ca` and `gateway.securedme.ca`; it does not confirm `education.securedme.ca` or `tesla-workbench.securedme.ca`. The public Education path remains `/product/education/`, and Tesla stays a separately tracked mismatch.
