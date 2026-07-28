# Contributing

## SecuredMe Education Governance

This repository is part of the SecuredMe Education suite and is currently pre-alpha. Contribution intake is intentionally conservative until the alpha classroom stability gate is reached.

- Tool: FNP-QNN Gateway MVP
- License: MIT License with SecuredMe school-governance constraints documented in this repository
- Local metadata reference: MIT
- Operational branch: main
- Official classroom AI routes: Codex/OpenAI and Antigravity/Gemini only
- Gateway stance: gateway-compatible when the shared SecuredMe gateway lane is configured; this repository must not store gateway secrets

## What Helps

Useful public issues include reproducible bugs, documentation gaps, test failures, accessibility problems, unclear student/teacher flows, and evidence-bound safety wording improvements.

Future code contributions should be small, test-backed, and scoped to this tool. They must preserve the suite hierarchy, the local secret boundary, human review, and the documented gateway contract.

## What Is Not Accepted

Do not submit or request:

- API keys, tokens, cookies, .env values, private cPanel details, private student data, or private correspondence;
- raw-token student flows or browser-session export;
- Ollama Cloud, uncensored local AI, unknown model providers, or unsupported agent routes as official school behavior;
- autonomous enforcement, clinical, regulatory, safety-critical, or production-readiness claims;
- offensive, abusive, fraud, bypass, credential theft, surveillance-abuse, or criminal automation workflows;
- broad rewrites that make the maintained classroom version harder to audit.

## Validation

Before maintainer-owned changes are pushed, run the narrow validation for this tool when available:

`powershell
python -m pytest
`

If the validation surface is not available on the machine, document the blocker in the issue or commit notes without inventing a passing result.

## Security Reports

Security issues must follow SECURITY.md. Do not publish exploit details, credentials, personal data, private files, or operational infrastructure details in a public issue.
