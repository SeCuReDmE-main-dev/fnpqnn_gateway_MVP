# Qodo Review Contract

## Mission

Perform an evidence-first, repository-wide review. This file governs every Qodo review, not only the current CodeProject.AI work. The repository is pre-alpha and will receive intensive changes; maximize useful technical information while avoiding cosmetic noise.

Project-specific focus: Gateway contract authority, secret-free routing, real HTTP/MCP calls without simulated success, stable error envelopes, and backward-compatible CLI behavior.

## Required finding format

For every finding, report all applicable fields:

1. Stable finding ID.
2. Severity: `BLOCKER`, `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`.
3. Confidence and the evidence that supports it.
4. Exact file and smallest useful line range.
5. Whether the defect is introduced by the current change or is pre-existing but directly exposed by it.
6. Reproduction steps, input, environment, and expected versus actual behavior.
7. Violated contract, invariant, security boundary, or documented requirement.
8. Concrete user, data, security, operational, or compatibility impact.
9. Smallest safe remediation, including affected interfaces and migration concerns.
10. Exact tests that should fail before the fix and pass afterward.

Never reproduce a credential or secret value. If one is detected, identify only its location, category, and required containment action.

## Mandatory review coverage

Review every changed path and its direct callers, consumers, tests, schemas, configuration, and documentation. Check:

- correctness, edge cases, state transitions, error handling, idempotency, retries, timeouts, cancellation, and concurrency;
- architecture boundaries, hidden coupling, duplicated authority, shared mutable state, and dependency direction;
- API, MCP, CLI, event, database, JSON Schema, and frontend/backend contract compatibility;
- authentication, authorization, tenant isolation, youth privacy, consent, input validation, injection, path traversal, SSRF, unsafe deserialization, and secret handling;
- data integrity, migrations, rollback behavior, provenance, retention, redaction, logs, telemetry, and failure recovery;
- CPU, memory, disk, network, startup cost, blocking I/O, unbounded collections, large payloads, and resource cleanup;
- dependency provenance, pinned versions, lockfile consistency, license impact, vulnerable packages, and supply-chain risk;
- tests for allowed and forbidden paths, negative cases, integration behavior, deterministic replay, and regression coverage;
- frontend loading, empty, error, offline, keyboard, focus, screen-reader, responsive, and reduced-motion behavior where applicable;
- documentation accuracy, safety claims, README badges, examples, commands, paths, and statements that are stronger than the available evidence;
- CI and operational scripts for platform assumptions, destructive commands, missing gates, and false-positive success.

Do not approve based only on a successful build, fixture, mocked transport, manifest validation, or README statement.

## SecuredMe Education invariants

- Official school AI routes are Codex/OpenAI and Antigravity/Gemini only.
- Do not introduce Ollama, OpenClaw, uncensored providers, raw student tokens, or unknown agent routes.
- Never expose `.env` values. Configuration and secrets must remain behind the approved Settings boundary.
- Preserve human review. AI output must not become autonomous grading, discipline, diagnosis, enforcement, or safety-critical authority.
- Keep this repository independent. Do not couple it to sibling source trees, private archives, retired `modele` paths, or another repository's mutable files.
- Changes must remain compatible with direct work on `main`; do not recommend a branch or pull request as the remediation.
- Datadog must be asynchronous, redacted, bounded, and fail-open. Its failure must never block the primary application path.
- CodeProject.AI must be a real local server when declared operational: pinned image digest, independent configuration and module volumes, health proof, real YOLO inference, stable connector errors, and mesh degradation handling.
- A fake, heuristic, dry-run, mocked, metadata-only, or documentation-only CodeProject.AI path must never be reported as live.
- Raw images, learner content, detections, audio, credentials, and private payloads must not enter telemetry.

## Review completeness report

End every review with:

- commits or diff reviewed;
- files and interfaces inspected;
- tests and commands executed with their exact result;
- security and privacy checks performed;
- areas not inspected and the precise reason;
- assumptions that still require runtime proof;
- ordered list of blocking findings;
- explicit verdict: `BLOCKED`, `CHANGES_REQUIRED`, or `VERIFIED_WITH_EVIDENCE`.

Use `VERIFIED_WITH_EVIDENCE` only when all relevant tests and runtime gates have actually passed. Absence of a finding is not proof that an untested surface works.

