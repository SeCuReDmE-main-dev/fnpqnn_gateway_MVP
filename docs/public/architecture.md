# Architecture

A narrow Python gateway converts reviewed client requests into typed simulator and audit operations.

It also owns the `securedme.education.auth-enforcer.v1` audit boundary. All twelve catalog repositories carry Codex and Antigravity `securedme.education.webauth-template.v1` adapters. The Gateway validates policy shape and secret exclusions; it does not impersonate an identity provider or absorb application sessions.

## Data flow

```text
Reviewed input -> typed boundary -> tool mechanism -> reviewable artifact -> human decision
```

```text
application adapter -> Gateway policy/audit -> provider-native web authentication
                    -> fingerprinted approval -> bounded tool capability
```

Adapter presence is not runtime proof. A product may claim live login only after its provider callback, account binding, expiry, logout, recovery, and accessibility paths pass in that product's deployed environment.

## Provenance

Record the repository commit, configuration, input identifiers, execution command, output location, and validation result. A screenshot alone is not a reproducible artifact.

## Failure behavior

Missing configuration, unavailable dependencies, invalid input, and failed tests must remain visible. The tool must not replace a failure with invented success.
