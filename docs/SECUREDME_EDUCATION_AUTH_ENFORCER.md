# SecuredMe Education Auth Enforcer

Status: pre-alpha closure procedure
Owner repo: `FNP-QNN-MVP/fnpqnn_gateway_MVP`
Contract: `securedme.education.auth-enforcer.v1`

## Scope

The Education suite auth/login mechanism is standardized on WebAuth, fingerprint acceptance, Token Governor enforcement, and Datadog side-channel observability.

The canonical suite contains 12 repositories:

1. `Synthia/Synthia`
2. `FNP-QNN-MVP/FNP-QNN-MVP`
3. `FNP-QNN-MVP/fnpqnn_gateway_MVP`
4. `FfeD-QLC-MVP`
5. `securedme-scholarium`
6. `QuaNThoR`
7. `VisualAlgorithmDesigner`
8. `algorithm-builder-app`
9. `algoquest-ams-discovry-labs-module-`
10. `V.O.T-Guardian`
11. `market-guardian-retailguard`
12. `tesla-resonance-recovery-workbench`

`fnpqnn_gateway_MVP` is the `auth_enforcer_owner` for the suite and owns the shared audit commands.

## Required Surfaces

Every repository must expose both platform surfaces:

- `.codex/webauth-template.json`
- `.codex/securedme-adapter-map.json`
- `.antigravity/webauth-template.json`
- `.antigravity/securedme-adapter-map.json`

The required adapter-map contract is `securedme.education.adapter-map.v2`.

## Enforcement Invariants

- `selected_auth_source` is `web-auth`.
- Fingerprint acceptance is mandatory.
- `raw_secret_stored` is always `false`.
- Forbidden material includes `oauth_token`, `cookie`, `browser_session`, `api_key`, `.env`, and `client_secret`.
- Token Governor is active through `gateway.token_governor_bridge`.
- `mcp.status` remains `planned` until a live MCP is connected.
- Auth failure policy is `deny_on_auth_contract_failure`.
- Telemetry failure policy is `fail_open`.
- The neutrosophic hierarchy is preserved exactly as `I -> I_system^S -> D_f -> dF -> i_fractal`.

## Commands

Run the full suite audit:

```powershell
python -m fnpqnn_gateway_mvp --json gateway suite-auth-audit --root "C:\Users\jeans\Desktop\Case study\modele"
```

Run a single surface check:

```powershell
python -m fnpqnn_gateway_mvp --json gateway suite-auth-check --root "C:\Users\jeans\Desktop\Case study\modele" --repo "FNP-QNN-MVP/fnpqnn_gateway_MVP" --platform codex
```

Both commands are read-only by default. `--write-diagnostics` writes a redacted local JSONL failure log under `.fnpqnn_gateway/auth_enforcer/`.

## Datadog Protection Model

Datadog is not an inline blocker for user or model calls. It protects the mechanism through metrics, dashboards, monitors, and Codex diagnostics after events are emitted.

DogStatsD events:

- `securedme.education.auth.enforcer_check`
- `securedme.education.auth.secret_reject`
- `securedme.education.auth.adapter_drift`
- `securedme.education.auth.template_missing`
- `securedme.education.auth.telemetry_drop`

Allowed tags:

- `repo`
- `platform`
- `decision`
- `env`
- `route`

High-cardinality values, raw user content, prompts, tokens, cookies, session IDs, client secrets, and `.env` values are forbidden in metrics, logs, and tags.

## Closure Gate

Before closing the auth/login development point:

1. Run `python -m unittest tests.test_gateway_cli` in Gateway.
2. Run the suite auth audit against the modele root.
3. Run controller and cPanel mesh tests.
4. Scan tracked files for secret payloads.
5. Confirm no `.env`, token, cookie, session, or secret material is tracked by Git.

