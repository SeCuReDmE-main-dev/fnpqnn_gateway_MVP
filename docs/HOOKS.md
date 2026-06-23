# Hook Contract

Runtime hooks are declared in `fnpqnn_gateway_mvp/hooks.py`.

## Runtime Hooks

- `simulator`: starts or diagnoses the base FNP-QNN simulator without AI account coupling.
- `codex`: checks OpenAI/Codex support and emits the Codex wake prompt path before simulator launch.
- `gemini`: checks Google/Gemini support and emits the Gemini wake prompt path before simulator launch.
- `ollama-cloud`: checks Ollama support and emits the Ollama wake prompt path before simulator launch.
- `openclaw`: checks OpenClaw/MCP surfaces before simulator launch.
- `agent-platform`: checks external agent platform surfaces such as OpenClaw/MCP manifests.
- `codeproject-ai`: observes or calls one CodeProject.AI Server HTTP backend.
- `codeproject-ai-mesh`: observes or calls a CodeProject.AI Server mesh backend and prints mesh guidance.

## Non-Hooks

`github-copilot` is an auth/support provider. It is not a runtime hook in v1 because Copilot is an IDE/account assistant surface, not a direct simulator backend.

## Activation Gate

Hooks are selected by `fnpqnn gateway activate` after a fingerprint is accepted:

- `codex` opens the `codex` hook and writes Codex-oriented onboarding.
- `gemini` opens the `gemini` hook and writes Gemini/Antigravity-oriented onboarding.
- `antigravity` opens the `antigravity` hook and writes IDE-native Antigravity onboarding.
- `ollama` opens the `ollama` hook and writes local Ollama onboarding.
- `ollama-cloud` opens the `ollama-cloud` hook and writes Ollama/OpenClaw-oriented onboarding.
- `github-copilot` keeps the runtime hook on `simulator` and writes IDE-oriented onboarding.
- `openclaw` opens the `openclaw` hook and writes OpenClaw-native onboarding.
- `codeproject-ai` and `codeproject-ai-mesh` write backend/tunnel/mesh onboarding.

The selected agent remains native. The gateway only exposes simulator capability paths, wake prompts, and hook commands.

## Bootstrap And Start

`fnpqnn gateway bootstrap` stores the accepted route in
`.fnpqnn_gateway/bootstrap.json`. `fnpqnn gateway start` reads that file and
launches the selected runtime in the foreground.

Bootstrap profile mapping:

- `natural` -> `simulator`
- `codex` -> `codex`
- `antigravity` -> `antigravity`
- `vscode` -> Copilot support-only plus CodeProject.AI Server tunnel metadata
- `ollama-cloud` -> `ollama-cloud`
- `openclaw` -> `openclaw`
- `cloud-kit` -> OpenClaw route plus E2B/CloudKit preflight
- `docker-kit` -> Docker Compose simulator API and Panel

## Safety Rules

- Commands are represented as argv lists, not shell strings.
- Runtime commands support dry-run plans before execution.
- Provider auth diagnostics do not store or print raw tokens.
- CodeProject.AI mesh diagnostics do not edit `appsettings.json` in v1.
