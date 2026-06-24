# QLC Wiring Pass 2

`fnpqnn gateway qlc-submit` now treats QLC workflow fixtures as a stable local contract.

- `--dry-run` validates the bundle and builds a compact loop receipt.
- `--timeout` must be greater than zero for real simulator submission.
- `--env-file` defaults to `C:\Users\jeans\.openclaw\workspace\.env` and reports only key presence.
- `--emit-metrics` emits DogStatsD counters with redacted tags only.

The gateway never prints raw API keys, raw media, full OCR, screenshots, browsing history, passwords, tokens, or full activity dumps.
