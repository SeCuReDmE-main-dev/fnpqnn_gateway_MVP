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
```

## Design boundary

This repo does not import the FNP-QNN simulator and does not copy CodeProject.AI Server. It calls external runtimes over CLI or HTTP. CodeProject.AI Server is treated as a local, network, mesh, or tunnel backend, not as a provider login.

GitHub Copilot is exposed as an auth/support provider only. It is intentionally not a runtime hook.
