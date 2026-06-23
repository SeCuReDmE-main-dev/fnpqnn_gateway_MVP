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
