# SecuredMe Commerce and Unified Identity

## Runtime boundaries

- `paypal.securedme.ca` serves the commerce endpoints and never exposes provider credentials to a browser.
- `gateway.securedme.ca` serves OIDC discovery, JWKS, authorization-code exchange, and explicit identity linking.
- Both hosts may route to `python -m fnpqnn_gateway_mvp.commerce_server`; the public host determines the edge route.
- The twelve registered clients use Authorization Code with PKCE S256 and exact HTTPS callback URLs.
- Google, GitHub, and PayPal identities remain separate until a signed-in user records explicit linking consent. Email similarity is never an account merge signal.
- ChatGPT contextual identity is accepted only when the trusted host supplies a verified context attestation.

## Public endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/v1/support/orders` | One-time PayPal support, including custom CAD amounts |
| `POST` | `/v1/support/subscriptions` | Monthly PayPal plan for 5, 10, or 25 CAD |
| `POST` | `/v1/diagnostics/orders` | Fixed 300 CAD diagnostic |
| `POST` | `/v1/paypal/webhooks` | PayPal-verified event ingestion |
| `POST` | `/v1/square/webhooks` | HMAC-verified Square Tap to Pay event ingestion |
| `GET` | `/v1/payments/{receiptId}` | Public-safe receipt state |
| `POST` | `/v1/intakes` | Advisory score with mandatory human review |
| `POST` | `/v1/projects/{id}/escrow` | Escrow.com two-milestone contract preview |
| `GET` | `/.well-known/openid-configuration` | OIDC discovery |
| `GET` | `/oidc/jwks.json` | ES256 public signing key |
| `POST` | `/oidc/authorize` | Issue one upstream-verified, PKCE-bound code |
| `POST` | `/oidc/token` | One-time code exchange |
| `POST` | `/v1/identity-links` | Explicit consent-based account linking |

All mutating payment requests require `Idempotency-Key`. Browser CORS is limited to HTTPS origins on `securedme.ca`.

## Secret-safe deployment variables

The repository root `.env` is the local reference only. Production values belong in the host secret store and must never be committed or logged.

```text
SECUREDME_COMMERCE_DB
OIDC_SIGNING_KEY_PATH
PAYPAL_CHECKOUT_MODE
PAYPAL_CHECKOUT_CLIENT_ID
PAYPAL_CHECKOUT_CLIENT_SECRET
PAYPAL_CHECKOUT_WEBHOOK_ID
PAYPAL_PLAN_5_CAD
PAYPAL_PLAN_10_CAD
PAYPAL_PLAN_25_CAD
SQUARE_ACCESS_TOKEN
SQUARE_LOCATION_ID
SQUARE_WEBHOOK_SIGNATURE_KEY
SQUARE_WEBHOOK_URL
ESCROW_API_KEY
ESCROW_API_EMAIL
```

The ES256 signing key must be generated outside the repository, restricted to the service account, and rotated with a JWKS overlap period. Square remains physical-only; no Square online checkout appears on public pages.

## Validation

```powershell
& "C:\Users\jeans\Desktop\Case study\modele\.venv\Scripts\python.exe" -m unittest tests.test_commerce tests.test_identity_broker -v
& "C:\Users\jeans\Desktop\Case study\modele\.venv\Scripts\python.exe" -m fnpqnn_gateway_mvp --json gateway suite-auth-audit --root "C:\Users\jeans\Desktop\Case study\modele"
```

Tap to Pay requires a compatible Square POS phone, an Internet connection, a low-value real transaction, and a refund test before production acceptance.

