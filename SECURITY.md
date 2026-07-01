# Security And Safety

Report security issues privately to the maintainer before public disclosure.

This gateway must remain credential-blind. It may store accepted fingerprints and local handoff metadata, but it must not store raw provider tokens, cookies, browser sessions, passwords, or secret environment values.

Official school providers are Codex/OpenAI and Antigravity/Gemini only.

## Token Governor Boundary

The Token Governor is a context-shaping layer, not an authentication layer. It
must reject or redact model-visible content that contains API keys, OAuth
tokens, cookies, browser sessions, passwords, `.env` values, or secret
environment material. It may write local policy snapshots, token estimates,
compression receipts, and artifact pointers under `.fnpqnn_gateway/token_governor`.
Those artifacts must not contain provider credentials or raw browser state.
