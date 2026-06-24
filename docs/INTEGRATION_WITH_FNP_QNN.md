# Integration With FNP-QNN

The gateway is a separate repo and package. It talks to the simulator through external CLI and HTTP boundaries only.

## Simulator Boundary

The base simulator must continue to work without AI accounts:

```powershell
fnpqnn gateway run --hook simulator --dry-run
```

AI-enabled hooks add diagnostics and wake-prompt routing, but they do not become required dependencies for the simulator core.

## QLC One-Way Submission

`fnpqnn gateway qlc-submit` is the one-way bridge from `FfeD-QLC-MVP` into the
simulator:

```text
QLC workflow bundle -> gateway validation -> POST /cerebrum/runtime/run
```

Accepted schemas:

- `ffed.qlc.protection_workflow_bundle.v1`;
- `ffed.qlc.gateway_submission.v1`.

The gateway extracts only `gateway_submission.mesh_payload`, fingerprints the
handoff, and returns a compact loop receipt for CeLeBrUm. It rejects raw images,
OCR text, videos, browsing/activity dumps, passwords, tokens, and secret keys.
Datadog tags are emitted as metadata labels such as schema, media type, SWOP
level, route action, simulator status, gateway mode, and E2B enabled state.

## External Agent Boundary

Codex, Gemini, Ollama Cloud, OpenClaw, MCP agents, CodeProject.AI Server, and CodeProject.AI mesh are support surfaces around the simulator. They should be replaceable without changing simulator internals.
