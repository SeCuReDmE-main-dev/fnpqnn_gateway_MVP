# Auth0 Cost Measurement Plan

The pilot records usage, not a promised invoice. Contractual pricing must be read from the accepted startup entitlement and the current Auth0 tenant dashboard before a purchasing decision.

## Measured Inputs

- Monthly active synthetic identities.
- Organizations.
- Login attempts, successes, failures, expirations, `401`, `403`, and `429` outcomes.
- Management API calls used by preflight and persona provisioning.
- Machine-to-machine clients and token issuance.
- Log retention actually available in the tenant.
- Availability and latency observed by the readiness probe.

## Decision Table

| Decision | Evidence required |
| --- | --- |
| Keep the pilot | Five personas work and usage stays inside the verified entitlement |
| Expand to 12 tools | Two pilots pass all security, accessibility, outage, restore, and browser tests |
| Present to a school board | Data map, privacy review, support model, contractual price, and synthetic demo are complete |
| Buy a higher tier | Observed usage or required institutional controls exceed the verified entitlement |
| Replace Auth0 | Cost, lock-in, outage behavior, or required controls fail the documented thresholds |

`auth0_entitlement_snapshot.v1` records the safe tenant context. `auth0_usage_snapshot.v1` records PII-free Gateway usage. Neither schema contains a price because prices and startup credits can change.
