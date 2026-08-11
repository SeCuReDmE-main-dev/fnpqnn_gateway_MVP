# API and tool map

- `fnpqnn-gateway`: operator CLI.
- `fnpqnn-gateway-mcp`: schema-bound MCP server.
- `gateway suite-auth-audit`: read-only fleet adapter audit.
- `gateway suite-auth-check`: targeted adapter validation.
- `auth fingerprint accept`: explicit bounded approval state.
- CodeProject.AI routes: external HTTP/mesh backends, never identity providers.

The Gateway enforces contracts; each application owns its deployed login callback and session lifecycle.
