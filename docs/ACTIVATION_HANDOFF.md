# Fingerprint Activation And Native Handoff

The gateway activation flow is deterministic:

```text
natural login -> fingerprint accepted -> tool route -> onboarding voice -> gate files -> native agent takeover
```

The gateway does not impersonate Codex, Gemini, Ollama, Copilot, or CodeProject.AI. It prepares the workspace and gate metadata so the selected native tool can operate normally with FNP-QNN simulator capabilities available.

## Commands

Dry-run the route:

```powershell
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --dry-run
```

Accept a fingerprint from the auth surface:

```powershell
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --dry-run
```

Write activation state:

```powershell
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --write
```

List routes:

```powershell
fnpqnn gateway activation-routes
```

Persist and reuse a launch profile:

```powershell
fnpqnn gateway bootstrap --profile natural --fingerprint fp-natural --accept-fingerprint
fnpqnn gateway start
```

## Route Table

| Tool | Auth provider | Runtime hook | Native handoff |
| --- | --- | --- | --- |
| `simulator` | none | `simulator` | local simulator CLI/HTTP |
| `codex` | `openai` | `codex` | Codex stays native; gateway exposes simulator context |
| `gemini` | `google` | `gemini` | Gemini/Antigravity stays native; gateway exposes simulator context |
| `antigravity` | `google` | `antigravity` | Antigravity stays native; gateway exposes simulator context |
| `ollama` | `ollama` | `ollama` | local Ollama stays native; gateway exposes simulator context |
| `ollama-cloud` | `ollama` | `ollama-cloud` | Ollama/OpenClaw stays native; gateway exposes simulator context |
| `github-copilot` | `github-copilot` | `simulator` | Copilot stays in the IDE; simulator hook remains local |
| `agent-platform` | none | `agent-platform` | external platform stays native |
| `openclaw` | none | `openclaw` | OpenClaw stays native; gateway exposes simulator context |
| `codeproject-ai` | none | `codeproject-ai` | CodeProject.AI remains HTTP backend |
| `codeproject-ai-server` | none | `codeproject-ai-server` | CodeProject.AI Server remains HTTP backend |
| `codeproject-ai-mesh` | none | `codeproject-ai-mesh` | CodeProject.AI remains mesh backend |

## Bootstrap Profiles

| Profile | Activation route | Runtime behavior |
| --- | --- | --- |
| `natural` | `simulator` | Starts the natural simulator API |
| `codex` | `codex` | Runs Codex/OpenAI preflight, then starts simulator API |
| `antigravity` | `antigravity` | Runs Google/Antigravity preflight, then starts simulator API |
| `vscode` | `github-copilot` + CodeProject.AI tunnel metadata | Keeps Copilot support-only and validates the approved CodeProject.AI Server URL |
| `ollama-cloud` | `ollama-cloud` | Runs Ollama support preflight, then starts simulator API |
| `openclaw` | `openclaw` | Runs OpenClaw/MCP preflight, then starts simulator API |
| `cloud-kit` | `openclaw` | Checks E2B/CloudKit readiness, then starts simulator API |
| `docker-kit` | `simulator` | Runs `docker compose up --build simulator-api simulator-panel` |

## Files Written On `--write`

The activation layer writes:

- `.fnpqnn_gateway/activation.json`
- `.fnpqnn_gateway/bootstrap.json` when `gateway bootstrap` is used
- `.fnpqnn_gateway/gates/<tool>.json`
- `.fnpqnn_gateway/onboarding/<tool>.json`
- `.fnpqnn_gateway/prompts/<tool>_wake_prompt.md`
- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `MEMORY.md`

Existing files are not overwritten unless `--force` is passed.

## Native Takeover Rule

After activation, the selected agent works in its native tool. The gateway only supplies:

- route metadata;
- onboarding questions;
- wake prompt;
- simulator commands;
- runtime hook command plans;
- safe local state files.

Raw provider tokens are never stored.

## Native Skill Requests

For a request such as "create a skill to build simulator gates", the gateway creates a native handoff file:

```powershell
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create simulator gate skills with native Codex tooling." --write
```

The selected tool must execute its own skills/plugins. The simulator receives the result as gate artifacts, CLI/HTTP command plans, tests, and docs.
