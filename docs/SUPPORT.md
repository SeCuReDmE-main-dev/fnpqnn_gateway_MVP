# Support Providers

The support layer separates account/provider readiness from runtime hooks.

## Auth Providers

- `openai`: ChatGPT/Codex natural login or environment readiness.
- `google`: Gemini/Google AI account readiness.
- `ollama`: local/cloud Ollama readiness.
- `github-copilot`: VS Code Copilot, Copilot CLI, or GitHub CLI readiness.

## Runtime Hooks

Runtime hooks are listed by:

```powershell
fnpqnn gateway hooks
```

Copilot must remain absent from this hook list unless a future version defines a direct backend contract.
