# Integration With FNP-QNN

The gateway is a separate repo and package. It talks to the simulator through external CLI and HTTP boundaries only.

## Simulator Boundary

The base simulator must continue to work without AI accounts:

```powershell
fnpqnn gateway run --hook simulator --dry-run
```

AI-enabled hooks add diagnostics and wake-prompt routing, but they do not become required dependencies for the simulator core.

## External Agent Boundary

Codex, Gemini, Ollama Cloud, OpenClaw, MCP agents, CodeProject.AI Server, and CodeProject.AI mesh are support surfaces around the simulator. They should be replaceable without changing simulator internals.
