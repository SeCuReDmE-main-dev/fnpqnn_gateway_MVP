# Token Governor

The Token Governor keeps SecuredMe Education app handoffs compact before they
reach Codex/OpenAI or Antigravity/Gemini. It does not authenticate providers
and it does not store provider secrets.

## Core Contract

- Stable system context is placed before variable student, session, or simulator
  context so provider-side caching can work when available.
- Large app state is represented by artifact pointers. Model-visible output gets
  a summary, ids, preserved math fields, and next actions.
- Raw OAuth tokens, cookies, browser sessions, passwords, `.env` values, and API
  keys are rejected before a handoff envelope is built.
- Math and simulator summaries preserve `I -> I_system^S -> D_f -> dF -> i_fractal`.

## Commands

```powershell
fnpqnn token-governor profiles
fnpqnn token-governor policy --preset classroom
fnpqnn token-governor plan --route codex --payload '{"goal":"short question"}' --dry-run
fnpqnn token-governor check --route antigravity --payload-file .\payload.json
fnpqnn token-governor compress --route codex --activity simulation --payload-file .\history.json --dry-run
fnpqnn token-governor report
```

Use `--write` only when you want local `.fnpqnn_gateway/token_governor` artifacts
such as policy snapshots, the latest plan, or artifact pointers.

## Integration Points

The governor is attached to:

- `gateway capability-map`
- `gateway skill-request`
- `gateway deepsearch-skill`
- `auth login`
- `auth model-switch`

Each integration returns a `token_governor` object with budget, route, activity,
estimated token use, cache-candidate prefix size, and quality checks.

## Metrics

The governor reports compact metrics only:

- `input_tokens_est`
- `output_visible_tokens_est`
- `cache_candidate_prefix_tokens`
- `cache_hit_tokens` when a provider later returns that value
- `route`
- `activity`

Datadog emission uses sanitized tags and never includes raw payloads or secrets.
