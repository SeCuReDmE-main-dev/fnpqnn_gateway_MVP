# fnpqnn_gateway_MVP

Standalone gateway CLI for the FNP-QNN simulator MVP.

The package provides one `fnpqnn` command surface for:

- running or diagnosing gateway hooks for the simulator, Codex, Gemini, Ollama Cloud, external agent platforms, CodeProject.AI Server, and CodeProject.AI mesh;
- checking natural auth readiness for OpenAI/ChatGPT, Google/Gemini, Ollama, and GitHub Copilot without storing raw tokens;
- validating CodeProject.AI Server local, mesh, or tunnel URLs as HTTP backends;
- keeping the simulator usable without any AI account.

## Install for local development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e .
```

## CLI examples

```powershell
fnpqnn gateway hooks
fnpqnn gateway run --hook simulator --dry-run
fnpqnn gateway run --hook codeproject-ai --codeproject-url http://localhost:32168
fnpqnn gateway run --hook codeproject-ai-mesh --known-server ai-node-01 --known-server ai-node-02
fnpqnn codeproject status --url http://localhost:32168 --dry-run
fnpqnn codeproject mesh-status --url http://localhost:32168 --dry-run
fnpqnn codeproject tunnel --url http://localhost:32168 --dry-run
fnpqnn auth natural-login github-copilot --source auto
fnpqnn gateway activation-routes
fnpqnn gateway activate --tool codex --fingerprint fp-123 --accept-fingerprint --dry-run
fnpqnn auth fingerprint accept --tool codex --fingerprint fp-123 --write
fnpqnn gateway capability-map --tool antigravity
fnpqnn gateway capability-map --tool openclaw
fnpqnn gateway skill-request --tool codex --name simulator-gate-builder --goal "Create simulator gate skills with native Codex tooling." --dry-run
fnpqnn codeproject yolo-status --url http://localhost:32168 --dry-run
fnpqnn codeproject yolo-training-status --url http://localhost:32168 --dry-run
fnpqnn memory obsidian-init --tool codex --write
fnpqnn memory obsidian-record --tool codex --title "YOLO Cerebrum Gate" --content "Map detections into Cerebrum events." --tag yolo --write
fnpqnn memory obsidian-query --query "yolo cerebrum"
fnpqnn memory obsidian-lvfm-stream --query "yolo cerebrum"
```

## Design boundary

This repo does not import the FNP-QNN simulator and does not copy CodeProject.AI Server. It calls external runtimes over CLI or HTTP. CodeProject.AI Server is treated as a local, network, mesh, or tunnel backend, not as a provider login.

GitHub Copilot is exposed as an auth/support provider only. It is intentionally not a runtime hook.

## Fingerprint activation

After a natural login is approved, `fnpqnn auth fingerprint accept` maps the accepted fingerprint to the chosen tool, writes gateway state and onboarding files, then leaves the selected agent in its native surface. Codex uses Codex, Gemini uses Gemini/Antigravity, Ollama uses Ollama/OpenClaw, Copilot stays in the IDE, and the simulator functions are exposed through gateway state, docs, and runtime hook commands.

See `docs/ACTIVATION_HANDOFF.md`.

## Capability bridge

`fnpqnn gateway capability-map` and `fnpqnn gateway skill-request` keep each system in its lane:

- Codex uses native Codex skills/plugins to help the simulator.
- Antigravity/Gemini uses native IDE/agent features to help the simulator.
- Ollama/OpenClaw uses native model/platform routing to help the simulator.
- Copilot stays an IDE support surface while the simulator hook remains local.
- CodeProject.AI Server stays an HTTP or mesh backend.
- CodeProject.AI YOLO inference and `Training for YoloV5 6.2` use documented CodeProject.AI routes.

The gateway only provides the handoff contract, paths, prompts, and simulator command surface.

## Obsidian RAG bridge

`fnpqnn memory obsidian-*` creates a Markdown plus JSONL RAG surface under `.fnpqnn_gateway/obsidian_vault`. Native tools can admit memories into this vault, and the gateway/simulator can retrieve them later without scraping provider memory stores.

The LVFM stream command turns admitted notes into a candidate Cerebrum payload, so the Obsidian vault acts like a creek feeding the simulator's main LVFM river.

See `docs/OBSIDIAN_RAG_BRIDGE.md`.
