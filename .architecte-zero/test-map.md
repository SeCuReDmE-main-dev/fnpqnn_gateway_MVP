# Test map

- Run `.venv\Scripts\python -m pytest` for the committed Python suite.
- Run `gateway suite-auth-audit` against the suite root for twelve-adapter policy coherence.
- Run `gateway suite-auth-check` for a single host adapter.
- Scan tracked output for forbidden secret classes.
- Test provider callback, account binding, expiry, logout, recovery, and accessibility in each application separately; Gateway tests do not prove those flows.
