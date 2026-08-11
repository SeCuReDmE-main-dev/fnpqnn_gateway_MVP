# Data map

- `.fnpqnn_gateway/`: local generated operator state; never a public secret store.
- Fingerprint records: non-secret approval references only.
- Diagnostics: redacted and opt-in when `--write-diagnostics` is used.
- Raw OAuth tokens, cookies, browser sessions, API keys, `.env` values, and client secrets: forbidden.

No production identity database is declared by this repository.
