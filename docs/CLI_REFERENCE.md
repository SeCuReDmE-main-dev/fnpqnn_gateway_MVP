# CLI Reference

The installed console command is `fnpqnn`.

## Gateway

```powershell
fnpqnn gateway hooks
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

## CodeProject.AI

```powershell
fnpqnn codeproject status --url http://localhost:32168
fnpqnn codeproject mesh-status --url http://localhost:32168 --known-server ai-node-01
fnpqnn codeproject tunnel --url http://localhost:32168
```

The tunnel command validates a user-approved local or forwarded URL. It stores no credential and does not inspect VS Code secrets.

## Auth And Support

```powershell
fnpqnn auth natural-login github-copilot --source auto
fnpqnn auth natural-login github-copilot --source vscode
fnpqnn auth natural-login github-copilot --source copilot-cli
fnpqnn auth natural-login github-copilot --source gh
fnpqnn auth provider-status openai
fnpqnn support provider github-copilot
fnpqnn support all
```

Natural auth diagnostics report existing tool readiness. They never persist raw tokens.
