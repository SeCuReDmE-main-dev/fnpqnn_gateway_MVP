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

## Fingerprint Acceptance

`fnpqnn auth fingerprint accept` is the support-to-runtime bridge. It records that a user-approved fingerprint was accepted, chooses the proper route, and prepares onboarding files. It does not store provider tokens.

Example:

```powershell
fnpqnn auth fingerprint accept --tool github-copilot --fingerprint fp-123 --write
```

For Copilot, this prepares IDE guidance while keeping the simulator runtime hook local.
