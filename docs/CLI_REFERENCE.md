# CLI Reference

The installed console command is `fnpqnn`.

## Gateway

```powershell
fnpqnn gateway hooks
fnpqnn gateway activation-routes
fnpqnn gateway bootstrap-profiles
fnpqnn gateway bootstrap --profile natural --fingerprint fp-natural --accept-fingerprint
fnpqnn gateway bootstrap --profile codex --fingerprint fp-codex --accept-fingerprint
fnpqnn gateway bootstrap --profile antigravity --fingerprint fp-antigravity --accept-fingerprint
fnpqnn gateway bootstrap --profile vscode --fingerprint fp-vscode --accept-fingerprint --codeproject-url http://localhost:32168
fnpqnn gateway bootstrap --profile openclaw --fingerprint fp-openclaw --accept-fingerprint
fnpqnn gateway bootstrap --profile cloud-kit --fingerprint fp-cloud --accept-fingerprint --env-file ".env"
fnpqnn gateway bootstrap --profile docker-kit --fingerprint fp-docker --accept-fingerprint
fnpqnn gateway start --dry-run
fnpqnn gateway run --profile natural --dry-run
fnpqnn gateway run --last --dry-run
fnpqnn gateway capability-map --tool codex
fnpqnn gateway capability-map --tool antigravity
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create simulator gate skills with native Codex tooling." --dry-run
fnpqnn gateway skill-entry --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn gateway skill-entry --name test-skill --goal "Create a test skill contract" --last --write
fnpqnn gateway skill-create --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn gateway skill-create --name test-skill --goal "Create a test skill contract" --last --output-path .\skills --write
fnpqnn function skill-creator --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn gateway deepsearch-skill --query "validate this research" --system antigravity --dry-run
fnpqnn gateway deepsearch-skill --query "validate this research" --last-auth --write
fnpqnn function deepsearch --query "validate this research" --system docker --dry-run
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --dry-run
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --write
fnpqnn gateway doctor --hook simulator
fnpqnn gateway doctor --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway doctor --hook codeproject-ai-mesh --known-server ai-node-01
fnpqnn gateway qlc-submit --bundle .\qlc-workflow.json --dry-run
fnpqnn gateway qlc-submit --bundle .\qlc-workflow.json --simulator-url http://localhost:8000
fnpqnn gateway run --hook simulator --dry-run
fnpqnn gateway run --hook codex --dry-run
fnpqnn gateway run --hook gemini --dry-run
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

`gateway qlc-submit` accepts `ffed.qlc.protection_workflow_bundle.v1` or
`ffed.qlc.gateway_submission.v1`, rejects raw media/OCR/activity/secrets, and
posts only the `mesh_payload` to `POST /cerebrum/runtime/run`. The response is
compacted into fingerprints and a `ffed.qlc.gateway_celebrum_loop_receipt.v1`;
the gateway does not echo raw simulator payloads.

Bootstrap profiles persist the last accepted route in `.fnpqnn_gateway/bootstrap.json`.
`gateway start` reuses that state and streams the selected server in the
foreground. Supported bootstrap profiles are `natural`, `codex`,
`antigravity`, `vscode`, `openclaw`, `cloud-kit`, and
`docker-kit`.

`gateway skill-entry` creates `.fnpqnn_gateway/skill_entries/<name>.json`,
`.fnpqnn_gateway/skill_entries/<name>.md`,
`.fnpqnn_gateway/skill_exits/<name>.json`, and
`.fnpqnn_gateway/skill_exits/<name>.md` when `--write` is used. The entry
contract tells the companion what to build; the exit contract is where the
companion reports `created`, `planned`, or `blocked` status.

`gateway skill-create` extends that contract with a SKILL.md creation plan.
It supports `--profile <profile>` or `--last`, optional `--output-path`, and
optional `--resources scripts,references,assets`. It never installs
provider-specific assets unless `--write --create-files` is explicitly used.

`gateway deepsearch-skill` creates a native web-search/deepsearch contract for
the simulator from `--system <auth-system>` or the latest accepted authlog via
`--last-auth`. Codex/OpenAI and Google/Antigravity use provider-native web
search. Systems without an official school search route fall back to
`antigravity-gemini-google-search`. The function alias is
`fnpqnn function deepsearch`. `--write` creates
`.fnpqnn_gateway/deepsearch/<query>.json` and `.md`; no `.env`, token, cookie,
or API key material is read or written.

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
fnpqnn auth systems
fnpqnn auth login --system codex --dry-run
fnpqnn auth login --system e2b --open-browser --dry-run
fnpqnn auth login --system datadog --open-browser --dry-run
fnpqnn auth login --system google --open-browser --dry-run
fnpqnn auth login --system github --open-browser --dry-run
fnpqnn auth login --system docker --open-browser --dry-run
fnpqnn auth login --system all --dry-run
fnpqnn function auth-login --system cloud-kit --dry-run
fnpqnn auth provider-routes
fnpqnn auth model-switch --tool codex --fingerprint fp-123 --dry-run
fnpqnn auth model-switch --last --dry-run
fnpqnn function provider-switch --tool antigravity --fingerprint fp-google --dry-run
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --dry-run
fnpqnn auth fingerprint accept --tool gemini --fingerprint fp-123 --write
fnpqnn support provider github-copilot
fnpqnn support all
```

Natural auth diagnostics report existing tool readiness. They never persist raw tokens.

Fingerprint acceptance maps the approved login identity to the correct onboarding voice and runtime gate. The selected agent then continues in its native tool with simulator capabilities exposed by the gateway.

`auth login` creates a web-auth hook wrapper per system. Supported systems
include `natural`, `codex`, `antigravity`, `vscode`,
`openclaw`, `cloud-kit`, `docker-kit`, `codeproject-ai`, plus direct account
surfaces `e2b`, `datadog`, `google`, `github`, and `docker`. `--open-browser`
opens the system login URL. Validation checks that the hook uses HTTPS where a
provider login exists, stores no secret, reads no dotenv file, and requires no
manual `.env` edit.

`auth model-switch` and `function provider-switch` select the model provider
from either an explicit fingerprint route or the last accepted bootstrap. The
switch is web-auth first, then native login, then `petit-yolo-instructions`.
It never asks the user to paste a token, never asks the user to edit `.env`,
and does not read dotenv files for provider switching. Any managed environment
state is considered gateway-owned and may be produced only after a successful
web-auth fingerprint.

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
fnpqnn cloud e2b-smoke --env-file ".env"
fnpqnn cloud e2b-ingest-plan --tool codex --source https://example.com/data.csv --title "External data" --dry-run
fnpqnn cloud e2b-ingest-plan --tool openclaw --source https://example.com/data.csv --title "External data" --write
```

`e2b-status` checks whether `e2b`, `e2b_code_interpreter`, and `E2B_API_KEY` are visible without printing secret values.

`e2b-smoke` is a real E2B smoke path. It loads `E2B_API_KEY` from the approved dotenv or environment, creates a sandbox, runs a minimal Python marker, returns a non-secret sandbox id, and closes the sandbox.

`e2b-ingest-plan` does not fetch external data. It builds the next-step contract for external data normalization, Obsidian admission, and LVFM stream handoff.
