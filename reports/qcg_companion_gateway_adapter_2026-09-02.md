# QCG Companion gateway adapter validation

Date: 2026-09-02

Status: `PASS WITH UNRELATED OPTIONAL-ENVIRONMENT LIMIT`

## Scope

This receipt covers the separate FNP-QNN Gateway snapshot producer. It is not a
WebMCP-QCG feature, hackathon claim, browser-extension release, provider route,
OpenClaw integration or external-execution path.

## Proof

- Four adapter tests pass: construction, bounded navigation, invalid-input
  rejection and CLI output.
- The CLI-produced snapshot passes the actual WebMCP-QCG
  `snapshotSanitizer.js` allowlist as `qcg-console-snapshot.v2`.
- The projection contains no raw gateway payload, source, path, credential,
  browser state, provider output or consent.
- Navigation is limited to the seven QCG console views.
- Only bounded human messaging and evidence export are advertised; the adapter
  cannot authorize a decision or perform an external execution.

Commands:

```powershell
python -m unittest discover -s tests -p "test_qcg_companion_adapter.py" -v
# 4 tests: PASS

python -m fnpqnn_gateway_mvp --json gateway qcg-companion-snapshot `
  --session-id 21ce8a13-35d2-4b31-9eb0-a81af9629c64 `
  --view activity --validated-contracts 4
# QCG sanitizer compatibility: PASS
```

An isolated full-suite run completed 164 tests with 161 passes, two skips and
one unrelated optional-environment failure: the existing real E2B smoke test
detected configured availability while the optional `e2b` Python package was
not installed. No provider request ran, and no secret value was printed. The
adapter tests and sanitizer compatibility remained green.

## Residual boundary

This is a contract-level snapshot producer. An application-specific content
bridge and dedicated browser package remain future integration work. They must
not broaden permissions, copy secrets, expose source or change human authority.
