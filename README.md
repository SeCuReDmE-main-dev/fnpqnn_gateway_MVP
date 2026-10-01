# FNP-QNN Gateway

![FNP-QNN Gateway — SecuredMe Education](docs/assets/repository/readme-banner-2026.png)

[![License MIT](https://img.shields.io/badge/license-MIT-6F42FF)](LICENSE)
[![Pre-alpha](https://img.shields.io/badge/status-pre--alpha-0E7490)](AGENTS.md)
[![Issues](https://img.shields.io/github/issues/SeCuReDmE-main-dev/fnpqnn_gateway_MVP)](https://github.com/SeCuReDmE-main-dev/fnpqnn_gateway_MVP/issues)
[![Main history](https://img.shields.io/github/last-commit/SeCuReDmE-main-dev/fnpqnn_gateway_MVP/main)](https://github.com/SeCuReDmE-main-dev/fnpqnn_gateway_MVP/commits/main/)
[![SPONSORED BY E2B FOR STARTUPS](https://img.shields.io/badge/SPONSORED%20BY-E2B%20FOR%20STARTUPS-ff3001?style=for-the-badge&labelColor=black)](https://e2b.dev/startups)

Inspect and enforce shared sessions, allowed tools, consent and bounded specialist handoffs.

[Tool documentation](https://securedme-main-dev.github.io/securedme-scholarium/en/tools/fnpqnn-gateway/) · [Education hub](https://securedme.ca/product/education/)

Runtime: local development; the public Education hub lists no public runtime for this tool.

**Status:** pre-alpha, active public development. Public pages and a successful local test do not establish a deployed school service. E2B sponsorship recognition is separate from runtime availability and included quota.

## How it works

The Gateway exposes a Python CLI, identity contracts and an authenticated WebMCP discovery page. Audience-bound pointers and approvals are stored locally and expire; authentication fails closed.

## Local development

Record the checkout and existing changes before editing:

```powershell
git status --short --branch
git rev-parse HEAD
```

In a clean development checkout, use the committed lockfile or package manifest. The commands below are setup instructions, not a claim that every dependency or optional service has been verified:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run the relevant local checks from the repository root; the indicated `Set-Location` is needed only when starting from that root:

```powershell
python -m unittest discover -s tests -v
```

## Source map

- [fnpqnn_gateway_mvp/cli.py](fnpqnn_gateway_mvp/cli.py)
- [fnpqnn_gateway_mvp/identity_store.py](fnpqnn_gateway_mvp/identity_store.py)
- [fnpqnn_gateway_mvp/gateway_webmcp.py](fnpqnn_gateway_mvp/gateway_webmcp.py)
- [tests](tests)

## Practice exercise

With synthetic sessions, compare an allowed tool, a denied role and a consumed pointer. Verify the second pointer resolution is rejected.

During an individual course, learners choose suite tools to practice. The eight-week final project is the learner's own tool, submitted by the learner to an eligible hackathon after checking its age, AI, originality and licensing rules.

## Boundaries and privacy

Shared adapter metadata does not prove twelve deployed logins. Provider callback, account binding, expiry, logout, recovery and accessible browser acceptance still need live validation. The package license is MIT; school governance remains in the repository instructions.

The official school routes are Codex/OpenAI and Antigravity/Gemini with human review. Never distribute raw tokens, learner data, prompts or private correspondence. No hidden learner analytics are added. Public analytics require explicit consent; general autocapture and session replay remain disabled. Optional local technical telemetry is separate from learner records and product audit history.

See [AGENTS.md](AGENTS.md) and [SCHOOL_TOOL_GOVERNANCE.md](SCHOOL_TOOL_GOVERNANCE.md) for current authority and provider boundaries. Maintainer-authorized maintenance follows repository protections and required reviews. General contribution restrictions remain governed by [CONTRIBUTING.md](CONTRIBUTING.md).

## License, authorship and history

The repository's actual license is [MIT](LICENSE). Keep the license, attribution, notices and safety boundaries when reusing the code.

Jean-Sebastien Beaulieu · [ORCID 0009-0007-2904-0443](https://orcid.org/0009-0007-2904-0443) · [SecuredMe](https://securedme.ca/)

[README source before curation](docs/archive/README-before-curation-2026-09-30.txt) retains the exact previous text, implementation journals and attribution. It is historical: its old telemetry commands, readiness claims and contribution dates are not current operating instructions. [Presentation history](docs/repository-presentation-history-2026-09-30.md) retains previous badges. [GitHub social image](docs/assets/repository/github-social-preview-2026.jpg) accompanies this README.
