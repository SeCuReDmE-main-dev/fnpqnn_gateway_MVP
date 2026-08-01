# FNP-QNN Gateway

<div class="se-tool-header">
  <img src="../../_static/tools/fnpqnn-gateway/logo.png" alt="FNP-QNN Gateway identity">
  <div><strong>FNP-QNN Gateway</strong><span>local-api · api · version 0.1.0</span></div>
</div>

The shared CLI, MCP, and service boundary for controlled FNP-QNN access.

## Public status

- **Runtime:** `api`
- **Availability:** `pending`
- **License:** `LicenseRef-SEL-2.0`
- **Version:** `0.1.0`

<div class="se-actions">
  <a href="https://gateway.securedme.ca">Open technical surface</a>
  <a href="https://github.com/SeCuReDmE-main-dev/fnpqnn_gateway_MVP">Source</a>
  <a href="https://github.com/SeCuReDmE-main-dev/fnpqnn_gateway_MVP/issues">Issues</a>
</div>

## Interfaces

- fnpqnn-gateway CLI
- MCP server
- Typed adapter boundary

```{important}
The gateway transports and validates requests; it does not convert model output into scientific authority.
```

```{toctree}
:maxdepth: 2

quickstart
architecture
interfaces
operations
```
