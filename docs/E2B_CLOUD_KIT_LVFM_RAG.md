# E2B Cloud Kit LVFM RAG

The gateway uses E2B as an optional isolated compute lane for user-approved
external data. E2B is not a provider login like Codex, Gemini, Ollama, or
Copilot. It is a sandbox backend that can normalize or inspect data before the
result is admitted into the gateway memory stream.

## Contract

```text
approved external data source
-> E2B sandbox normalization or inspection
-> sanitized summary
-> fnpqnn memory obsidian-record
-> fnpqnn memory obsidian-lvfm-stream
-> simulator-side cloud-kit rag-runtime or rag-decrypt-runtime
-> Cerebrum/LVFM runtime owned by FNP-QNN
```

## Install

```powershell
.\.venv\Scripts\python -m pip install -e ".[cloud]"
```

## Real Smoke

```powershell
fnpqnn cloud e2b-smoke --env-file "C:\Users\jeans\.openclaw\workspace\.env"
```

The smoke loads `E2B_API_KEY` into the current process without printing it. If
the key exists, the gateway creates a real E2B sandbox, runs a marker command,
returns `sandbox_id`, verifies the marker, and closes the sandbox.

## Ingest Plan

```powershell
fnpqnn cloud e2b-ingest-plan --tool codex --source https://example.com/data.csv --title "External data" --dry-run
```

The plan records:

- selected native tool route;
- runtime hook;
- approved source URL or identifier;
- Obsidian admission command;
- LVFM stream command;
- boundaries for no raw tokens, no private memory scraping, and no unapproved
  source fetch.

## Encryption

Encryption is simulator-side because the simulator is the boundary that owns
LVFM ingestion. Use:

```powershell
.\.venv\Scripts\python.exe -m fnp_qnn_cli --json cloud-kit rag-keygen
.\.venv\Scripts\python.exe -m fnp_qnn_cli --json cloud-kit rag-encrypt --title "E2B normalized data" --source "e2b://sandbox/result" --tool-route codex --content-file .\summary.md
.\.venv\Scripts\python.exe -m fnp_qnn_cli --json cloud-kit rag-decrypt-runtime --envelope .\envelope.json
```

The gateway may prepare and route the handoff, but the simulator decides how an
admission becomes Cerebrum/LVFM state.
