# SecuredMe Gateway Observability Bootstrap

The shared SecuredMe gateway is the suite-level integration point for optional
E2B audit sandboxes and optional Datadog observability. Individual school tools
should not install or authenticate Datadog or E2B directly by default.

## Boundary

- Datadog and E2B are optional gateway lanes, not default per-tool runtime
  dependencies.
- Python wheel builds must not connect to MCP servers, Datadog, E2B, or any
  external secret store.
- Build and install steps must not read raw `.env` secrets.
- Bootstrap is an explicit post-install action and must support dry-run first.
- Codex/OpenAI and Antigravity/Gemini remain the official school agent routes.

## Proposed command shape

```powershell
securedme-gateway bootstrap observability --datadog-mcp --e2b-audit --dry-run
```

The first implementation should report only non-secret metadata:

- `datadog_mcp_configured`
- `datadog_mcp_authenticated`
- `e2b_audit_configured`
- `gateway_repo_detected`
- `school_tool_contract_detected`
- `dry_run`

It must never print API keys, OAuth tokens, cookies, `.env` values, raw Datadog
credentials, or E2B secrets.

## Protection Agent Direction

A future gateway protection agent may validate:

- install state;
- required environment presence as booleans only;
- source repository provenance;
- active branch and commit metadata;
- README support-block compliance;
- school governance contract presence;
- Datadog MCP availability when the current Codex or Antigravity session exposes
  the authenticated tool surface.

The protection agent is review support only. It must not auto-merge, auto-fix
secrets, bypass branch protections, or make claims that every tool directly uses
Datadog or E2B.
