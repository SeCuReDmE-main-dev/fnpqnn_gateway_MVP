# Auth0 Management API Scopes

Use two machine-to-machine applications. Do not reuse the Gateway runtime client.

## Deploy CLI Client

Grant only the resources managed by `AUTH0_INCLUDED_ONLY`:

- `read:clients`, `create:clients`, `update:clients`
- `read:resource_servers`, `create:resource_servers`, `update:resource_servers`
- `read:organizations`, `create:organizations`, `update:organizations`

Do not grant any `delete:*` scope. Keep `AUTH0_ALLOW_DELETE=false`.

## Synthetic Persona Provisioner

- `read:users`, `create:users`, `update:users`
- `read:organizations`, `read:organization_members`, `create:organization_members`
- `read:organization_connections`, `create:organization_connections`, `update:organization_connections`
- `read:connections`

Do not grant `delete:users`, `delete:organizations`, `delete:organization_members`, or any unrelated tenant-wide permission.

The exact scope names available in the tenant dashboard must be reviewed before authorization. If a listed scope is unavailable or Auth0 requests a broader scope, stop and document the discrepancy rather than widening permissions silently.
