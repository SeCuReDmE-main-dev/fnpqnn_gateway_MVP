# CLI Reference

The installed console command is `fnpqnn`.

## Gateway

```powershell
fnpqnn gateway hooks
fnpqnn gateway activation-routes
fnpqnn gateway capability-map --tool codex
fnpqnn gateway capability-map --tool antigravity
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create simulator gate skills with native Codex tooling." --dry-run
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --dry-run
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --write
fnpqnn gateway doctor --hook simulator
fnpqnn gateway doctor --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway doctor --hook codeproject-ai-mesh --known-server ai-node-01
fnpqnn gateway run --hook simulator --dry-run
fnpqnn gateway run --hook codex --dry-run
fnpqnn gateway run --hook gemini --dry-run
fnpqnn gateway run --hook ollama-cloud --dry-run
fnpqnn gateway run --hook agent-platform --dry-run
fnpqnn gateway run --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway run --hook codeproject-ai-mesh --codeproject-url http://localhost:32168 --known-server ai-node-01
```

Supported options:

- `--hook <name>` selects the runtime hook.
- `--host <host>` and `--port <port>` shape simulator command plans.
- `--codeproject-url <url>` defaults to `http://localhost:32168`.
- `--known-server <hostname>` may be repeated for mesh diagnostics.
- `--jsonl` streams event records as JSON lines.
- `--dry-run` prints the execution plan without starting a process.
- `--no-preflight` skips simulator/provider preflight commands.
- `--accept-fingerprint` is required by `gateway activate` before the route is considered open.
- `--write` writes `.fnpqnn_gateway` state and onboarding files.
- `--force` allows overwriting existing activation/onboarding files.

## CodeProject.AI

```powershell
fnpqnn codeproject status --url http://localhost:32168
fnpqnn codeproject mesh-status --url http://localhost:32168 --known-server ai-node-01
fnpqnn codeproject tunnel --url http://localhost:32168
fnpqnn codeproject yolo-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-status --url http://localhost:32168 --image .\sample.jpg
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --model-name my-model
```

The tunnel command validates a user-approved local or forwarded URL. It stores no credential and does not inspect VS Code secrets.

## Auth And Support

```powershell
fnpqnn auth natural-login github-copilot --source auto
fnpqnn auth natural-login github-copilot --source vscode
fnpqnn auth natural-login github-copilot --source copilot-cli
fnpqnn auth natural-login github-copilot --source gh
fnpqnn auth provider-status openai
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --dry-run
fnpqnn auth fingerprint accept --tool gemini --fingerprint fp-123 --write
fnpqnn support provider github-copilot
fnpqnn support all
```

Natural auth diagnostics report existing tool readiness. They never persist raw tokens.

Fingerprint acceptance maps the approved login identity to the correct onboarding voice and runtime gate. The selected agent then continues in its native tool with simulator capabilities exposed by the gateway.

## Memory / Obsidian

```powershell
fnpqnn memory obsidian-init --tool codex --dry-run
fnpqnn memory obsidian-init --tool codex --write
fnpqnn memory obsidian-record --tool codex --title "YOLO Cerebrum Gate" --content "Map detections into Cerebrum events." --tag yolo --tag cerebrum --write
fnpqnn memory obsidian-query --query "yolo cerebrum"
fnpqnn memory obsidian-lvfm-stream --query "yolo cerebrum"
```

The Obsidian bridge is a Markdown plus JSONL persistent RAG surface. It receives explicit admissions from native tools; it does not scrape their private memory stores.

`obsidian-lvfm-stream` converts matching admitted notes into a candidate Cerebrum/LVFM payload while leaving LVFM ownership inside the simulator.

## Cloud / E2B

```powershell
fnpqnn cloud e2b-status
fnpqnn cloud e2b-smoke --env-file "C:\Users\jeans\.openclaw\workspace\.env"
fnpqnn cloud e2b-ingest-plan --tool codex --source https://example.com/data.csv --title "External data" --dry-run
fnpqnn cloud e2b-ingest-plan --tool openclaw --source https://example.com/data.csv --title "External data" --write
```

`e2b-status` checks whether `e2b`, `e2b_code_interpreter`, and `E2B_API_KEY` are visible without printing secret values.

`e2b-smoke` is a real E2B smoke path. It loads `E2B_API_KEY` from the approved dotenv or environment, creates a sandbox, runs a minimal Python marker, returns a non-secret sandbox id, and closes the sandbox.

`e2b-ingest-plan` does not fetch external data. It builds the next-step contract for external data normalization, Obsidian admission, and LVFM stream handoff.
