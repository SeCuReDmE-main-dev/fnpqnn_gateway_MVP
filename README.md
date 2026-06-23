# fnpqnn_gateway_MVP

Standalone gateway CLI for the FNP-QNN simulator MVP.

The package provides one `fnpqnn` command surface for:

- launching the branded simulator TUI through `fnpqnn --tui` when the simulator package is installed;
- running or diagnosing gateway hooks for the simulator, Codex, Gemini, Ollama Cloud, external agent platforms, CodeProject.AI Server, and CodeProject.AI mesh;
- checking natural auth readiness for OpenAI/ChatGPT, Google/Gemini, Ollama, and GitHub Copilot without storing raw tokens;
- validating CodeProject.AI Server local, mesh, or tunnel URLs as HTTP backends;
- admitting Obsidian RAG notes with p114 neutrosophic T/I/F gate metadata;
- keeping the simulator usable without any AI account.

## Install for local development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m pip install -e ".[cloud]"
```

## CLI examples

```powershell
fnpqnn --tui
fnpqnn gateway hooks
fnpqnn gateway bootstrap --profile natural --fingerprint fp-natural --accept-fingerprint
fnpqnn gateway bootstrap --profile vscode --fingerprint fp-vscode --accept-fingerprint --codeproject-url http://localhost:32168
fnpqnn gateway bootstrap --profile ollama-cloud --fingerprint fp-ollama --accept-fingerprint
fnpqnn gateway bootstrap --profile openclaw --fingerprint fp-openclaw --accept-fingerprint
fnpqnn gateway start --dry-run
fnpqnn gateway run --hook simulator --dry-run
fnpqnn gateway run --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway run --hook codeproject-ai-mesh --known-server ai-node-01 --known-server ai-node-02
fnpqnn codeproject status --url http://localhost:32168 --dry-run
fnpqnn codeproject mesh-status --url http://localhost:32168 --dry-run
fnpqnn codeproject tunnel --url http://localhost:32168 --dry-run
fnpqnn auth natural-login github-copilot --source auto
fnpqnn auth systems
fnpqnn auth login --system e2b --open-browser --dry-run
fnpqnn auth login --system datadog --open-browser --dry-run
fnpqnn auth login --system google --open-browser --dry-run
fnpqnn auth login --system github --open-browser --dry-run
fnpqnn auth login --system docker --open-browser --dry-run
fnpqnn function auth-login --system cloud-kit --dry-run
fnpqnn auth provider-routes
fnpqnn auth model-switch --tool codex --fingerprint fp-123 --dry-run
fnpqnn auth model-switch --last --dry-run
fnpqnn function provider-switch --tool ollama-cloud --fingerprint fp-ollama --dry-run
fnpqnn gateway activation-routes
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --dry-run
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --write
fnpqnn gateway capability-map --tool antigravity
fnpqnn gateway capability-map --tool openclaw
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create simulator gate skills with native Codex tooling." --dry-run
fnpqnn gateway skill-entry --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn gateway skill-create --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn function skill-creator --name test-skill --goal "Create a test skill contract" --profile codex --dry-run
fnpqnn gateway deepsearch-skill --query "validate this research" --system ollama-cloud --dry-run
fnpqnn function deepsearch --query "validate this research" --last-auth --write
fnpqnn codeproject yolo-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --dry-run
fnpqnn memory obsidian-init --tool codex --write
fnpqnn memory obsidian-record --tool codex --title "YOLO Cerebrum Gate" --content "Map detections into Cerebrum events." --tag yolo --write
fnpqnn memory p114-consensus --item "verified evidence passed" --item "partial risk pending"
fnpqnn memory obsidian-query --query "yolo cerebrum"
fnpqnn memory obsidian-lvfm-stream --query "yolo cerebrum"
fnpqnn cloud e2b-status
fnpqnn cloud e2b-smoke --env-file "C:\Users\jeans\.openclaw\workspace\.env"
fnpqnn cloud e2b-ingest-plan --tool codex --source https://example.com/data.csv --title "External data" --dry-run
```

## Design boundary

This repo does not import the FNP-QNN simulator and does not copy CodeProject.AI Server. It calls external runtimes over CLI or HTTP. CodeProject.AI Server is treated as a local, network, mesh, or tunnel backend, not as a provider login.

GitHub Copilot is exposed as an auth/support provider only. It is intentionally not a runtime hook.

## Fingerprint activation

After a natural login is approved, `fnpqnn auth fingerprint accept` maps the accepted fingerprint to the chosen tool, writes gateway state and onboarding files, then leaves the selected agent in its native surface. Codex uses Codex, Gemini uses Gemini/Antigravity, Ollama uses Ollama/OpenClaw, Copilot stays in the IDE, and the simulator functions are exposed through gateway state, docs, and runtime hook commands.

See `docs/ACTIVATION_HANDOFF.md`.

`fnpqnn gateway bootstrap` is the persistent launch form of the same contract.
It writes `.fnpqnn_gateway/bootstrap.json` only after an accepted fingerprint,
and `fnpqnn gateway start` reuses the last accepted profile. Profiles include
`natural`, `codex`, `antigravity`, `vscode`, `ollama-cloud`, `openclaw`,
`cloud-kit`, and `docker-kit`.

`fnpqnn auth login` builds the web-auth hook wrapper for a selected system.
It supports the bootstrap systems and direct account systems `e2b`, `datadog`,
`google`, `github`, and `docker`. `--open-browser` opens the configured HTTPS
login target, while validation confirms the wrapper stores no secret, reads no
dotenv file, and never asks for a manual `.env` edit.

`fnpqnn auth model-switch` and the function-style alias
`fnpqnn function provider-switch` choose the model provider from a fingerprint
route or from the last bootstrap. Provider switching is web-auth first. It does
not ask the user to paste tokens or edit `.env`; any managed environment state
belongs to the gateway and is allowed only after a successful web-auth
fingerprint. If web auth and native login are unavailable, the fallback is
`petit-yolo-instructions`, a small instruction path that tells the operator
which provider web login to open without exposing secrets.

`fnpqnn gateway skill-entry` and `fnpqnn gateway skill-create` turn the active
bootstrap/fingerprint route into a companion skill contract. `skill-entry`
writes entry and exit contracts under `.fnpqnn_gateway/skill_entries` and
`.fnpqnn_gateway/skill_exits`. `skill-create` adds a SKILL.md plan with
required frontmatter, validation commands, optional resource folders, and the
same no-secret/no-provider-absorption boundary. The function-style alias is
`fnpqnn function skill-creator`.

`fnpqnn gateway deepsearch-skill` creates the simulator native web-search
contract from the selected authlog session. Ollama Cloud and
Google/Antigravity routes use their provider-native web-search surface; systems
without a declared native search route fall back to
`antigravity-gemini-google-search`. The alias is `fnpqnn function deepsearch`.
The contract is written under `.fnpqnn_gateway/deepsearch` only when `--write`
is used, and it never stores tokens, cookies, API keys, or `.env` material.

## Capability bridge

`fnpqnn gateway capability-map` and `fnpqnn gateway skill-request` keep each system in its lane:

- Codex uses native Codex skills/plugins to help the simulator.
- Antigravity/Gemini uses native IDE/agent features to help the simulator.
- Ollama/OpenClaw uses native model/platform routing to help the simulator.
- Copilot stays an IDE support surface while the simulator hook remains local.
- CodeProject.AI Server stays an HTTP or mesh backend.
- CodeProject.AI YOLO inference and `Training for YoloV5 6.2` use documented CodeProject.AI routes.

The gateway only provides the handoff contract, paths, prompts, and simulator command surface.

## Codex Native Handoff

This gateway is designed so Codex can remain a native Codex agent while still
controlling the simulator. The intended shape is:

```text
Codex native skills/plugins/git/debug workflow
-> fnpqnn gateway activation and capability map
-> allowlisted simulator CLI/HTTP commands
-> optional Obsidian RAG admission
-> simulator-owned Cerebrum/LVFM runtime
```

The gain is not that Codex replaces the simulator, or that the simulator
absorbs Codex. The gain is that Codex can use its native coding ability to
operate a quantum/neutrosophic simulator surface with clear gates, provenance,
and handoff files.

For example:

```powershell
fnpqnn gateway activate --tool codex --fingerprint fp-codex --accept-fingerprint --write
fnpqnn gateway capability-map --tool codex
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create a simulator skill that designs safe LVFM gates." --dry-run
```

The same pattern exists for Antigravity/Gemini, Ollama/OpenClaw, Copilot,
CodeProject.AI Server, and external agent platforms. Each native tool keeps its
own skills and interface. The gateway provides the route, prompts, docs, and
simulator-facing command contract.

## Obsidian RAG bridge

`fnpqnn memory obsidian-*` creates a Markdown plus JSONL RAG surface under `.fnpqnn_gateway/obsidian_vault`. Native tools can admit memories into this vault, and the gateway/simulator can retrieve them later without scraping provider memory stores.

The LVFM stream command turns admitted notes into a candidate Cerebrum payload, so the Obsidian vault acts like a creek feeding the simulator's main LVFM river.

Every `obsidian-record` admission now runs the local
`p114_ffed_neutrosophic_consensus` gate by default when the FFeD pluginpack is
available. The generated Markdown frontmatter includes:

- `fnpqnn_t`;
- `fnpqnn_i`;
- `fnpqnn_f`;
- `fnpqnn_df`;
- `fnpqnn_gate`;
- `fnpqnn_action`.

The JSONL index carries the same gate payload, and `obsidian-lvfm-stream`
forwards it as Cerebrum event metadata. This keeps the Obsidian path human
readable while still giving the simulator a precise neutrosophic admission
trace. Pass `--neutrosophic-gate none` only for low-level transport tests.

See `docs/OBSIDIAN_RAG_BRIDGE.md`.

## TUI Branding

`fnpqnn --tui` delegates to the simulator Textual TUI when `fnp_qnn_cli` is
installed in the active Python environment. The visual identity is derived from
the simulator assets:

- large source logo: `assets/logo/Logo version 2.png`;
- small source logos: `assets/logo/Logo 3 .png`,
  `assets/logo/banner small.png`, and `assets/logo/FNP-QNN logo.png`;
- palette: ink navy, off-white paper, fine gold linework, and restrained
  quantum-blue accents.

The terminal uses an ASCII vector imprint rather than embedding PNG pixels, so
the TUI remains portable across PowerShell, Windows Terminal, VS Code terminals,
and remote tunnel sessions.

## E2B Cloud Kit

The gateway has an optional cloud extra for E2B:

```powershell
.\.venv\Scripts\python -m pip install -e ".[cloud]"
```

E2B is treated as an isolated compute lane for approved external data. It is
not an AI account provider and it is not a replacement for the simulator. The
current flow is:

```text
approved external source
-> real E2B sandbox smoke or normalization job
-> sanitized summary
-> Obsidian RAG admission
-> LVFM stream candidate
-> simulator receives Cerebrum payload through its own API/CLI
```

Commands:

```powershell
fnpqnn cloud e2b-status
fnpqnn cloud e2b-smoke --env-file "C:\Users\jeans\.openclaw\workspace\.env"
fnpqnn cloud e2b-ingest-plan --tool codex --source https://example.com/data.csv --title "External data" --dry-run
```

The smoke command is real: when `E2B_API_KEY` is present in the approved dotenv
or current environment, the gateway creates an E2B sandbox and runs a minimal
Python marker command. Output includes a non-secret `sandbox_id` and
`stdout_contains_expected_marker`; it never prints the key.

The ingest plan does not fetch unapproved data. It creates the operational
contract and the exact next commands for:

- `fnpqnn memory obsidian-record`
- `fnpqnn memory obsidian-lvfm-stream`

The simulator-side encryption and LVFM conversion lives in the main
`FNP-QNN-MVP` repo under `core/cloud_rag_bridge.py` and CLI commands
`fnp-qnn cloud-kit rag-*`.
