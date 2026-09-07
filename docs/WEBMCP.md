# Gateway WebMCP control plane

The Gateway serves a real discovery page at `/webmcp` and a machine manifest at
`/api/v1/webmcp/manifest`. Discovery is available before login. Invocation at
`/api/v1/webmcp/invoke` requires the host-only Gateway session cookie, a valid
rotated CSRF token, consent scope, and the exact `gateway` entry in
`allowed_tools`.

The manifest contains ten Gateway tools backed by `IdentityStore`, the bounded
CodeProject.AI contract, or `GatewayWebMCPStore`, plus the two shared companion
tools. It deliberately exposes no image-path detector, shell, `.env`, E2B,
provisioner, provider token, browser automation, or identity merge capability.

`GatewayWebMCPStore` creates additive SQLite tables only. Approval receipts bind
session, tool, payload digest and idempotency key, expire within five minutes,
and are consumed once. Opaque pointers are sanitized, audience-bound, consumed
once, and expire within five minutes. Provider identities remain separate.

No product-specific Gateway Stitch folder exists in the verified Education
landing asset directory. The page therefore records and consumes the SecuredMe
accessible fallback identifier
`securedme-site/theme-fallbacks/securedme-education-accessible.v1` with
`sourceStatus: fallback-no-product-stitch-found`: navy surface, blue focus,
paper-white text, system fonts, visible focus, and no image-dependent meaning.
