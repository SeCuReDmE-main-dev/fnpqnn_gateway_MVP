# Auth0 Gateway Pilot

## Boundary

Auth0 authenticates an upstream human. The SecuredMe Gateway authorizes that identity for educational work. AlgoQuest and Synthia never receive Auth0 access tokens, refresh tokens, client secrets, email addresses, dates of birth, or complete educational histories.

The browser receives only `securedme.education.session.v2`: a pseudonymous identity reference, internal role, derived age band, authority, consent scope, assigned tools, optional pseudonymous class/student references, session timestamps, and a CSRF value.

## Development Surfaces

| Surface | Purpose | Production impact |
| --- | --- | --- |
| `gateway-dev.securedme.ca` | Server-side OIDC callback and SecuredMe session | None until deployed and approved |
| `algoquest-dev.securedme.ca` | Student/teacher pilot client | None |
| `synthia-dev.securedme.ca` | Synthetic professor cockpit pilot | None |

Every surface must use HTTPS and `noindex`. CORS and `return_to` are exact lists, not wildcard or suffix matches.

## Authentication Flow

1. The pilot calls `GET /api/v1/session` with credentials.
2. A `401` sends the human to `GET /auth/login?return_to=<registered URL>`.
3. The Gateway stores `state`, `nonce`, PKCE verifier, organization, return URL, and a hashed browser binding server-side.
4. Auth0 Universal Login authenticates the human in the synthetic organization.
5. `/auth/callback` validates RS256/JWKS, issuer, client audience, expiration, nonce, organization, one-time state, and the allowed identity-connection prefix. When Auth0 supplies `amr`, it is also checked against the configured allowlist.
6. The Gateway maps `(issuer, subject)` to a durable `securedme_id` and projects the current internal assignment into a host-only session.
7. AlgoQuest or Synthia accepts the session only when its slug is present and the authorization decision is `allow`.

## Endpoints

- `GET /auth/login`
- `GET /auth/callback`
- `GET /api/v1/session`
- `POST /auth/logout` with `X-CSRF-Token`
- `POST /api/v1/identity-links` with `X-CSRF-Token`; returns a bounded refusal until a second provider proof exists
- `GET /api/v1/auth/usage` for privacy or school administrators
- `GET /health/live`
- `GET /health/ready`

The internal OIDC endpoints remain available. `/oidc/authorize` now requires a verified Gateway session. The old verification header exists only when `SECUREDME_ALLOW_LEGACY_IDENTITY_HEADER_FOR_TESTS=true`.

## Tenant Procedure

Run all commands from `infra/auth0` with secrets supplied by Settings:

```powershell
npm ci
npm run preflight
npm run export
npm run dry-run
```

Preflight refuses a tenant that is not explicitly `Development`, contains non-synthetic users, contains an unrelated organization, or enables deletion. The private export under `snapshots/` is gitignored.

Only after reviewing the export and dry-run:

```powershell
$env:SECUREDME_AUTH0_IMPORT_CONFIRMATION='IMPORT_DEVELOPMENT_SYNTHETIC_TENANT'
npm run import
$env:SECUREDME_AUTH0_PERSONA_CONFIRMATION='CREATE_FIVE_SYNTHETIC_PERSONAS'
npm run personas
```

The provisioner creates or reuses five synthetic identities, enables the selected database connection for the organization with open signup disabled, enrolls the personas in `securedme-synthetic-school`, and stores roles/classes only in the separate SecuredMe identity database. Passwords come from environment settings and are never printed.

## Pilot Data

Synthia's current class/evidence records are synthetic. They remain unavailable unless `VITE_SECUREDME_SYNTHETIC_PILOT=true`. This flag permits the fixture dataset; it does not bypass the Gateway session or tool authorization.

## Failure Semantics

- Auth0 unavailable: `/health/live` stays live, `/health/ready` becomes unavailable, and new logins fail closed.
- Existing Gateway session: valid until its local expiry or revocation; no refresh token is held in the browser.
- No internal assignment: authenticated but authorization is `deny`.
- Wrong organization, audience, nonce, signature, expiration, origin, return URL, or CSRF: rejected.
- Missing pilot tool in `allowed_tools`: client refuses the session.

## Restore

Before tenant import, keep the private Deploy CLI export. Before replacing the identity database, stop the Gateway and copy the SQLite file with its `-wal` and `-shm` companions when present. Restore means replacing the local SQLite set and importing the reviewed Auth0 snapshot only into the same Development tenant. Production restoration is outside this pilot.

## Expansion Gate

The ten remaining tools may adopt the browser session client only after all five personas pass login, authorization, expiration, logout, CORS, CSRF, accessibility, desktop/mobile Playwright, outage, and restore tests on these two pilots. No tool receives an Auth0 SDK or provider token.
