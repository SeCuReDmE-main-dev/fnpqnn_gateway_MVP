# QCG Companion gateway adapter

The gateway can now produce a bounded `qcg-console-snapshot.v2` projection for
the QCG Companion pattern. This is a separate, dry-run adapter proof. It does
not modify WebMCP-QCG, rename QCG, install a browser extension, call a provider,
or become part of the hackathon submission path.

## Boundary

The producer accepts only a UUID, fixed navigation enums, a fixed gateway state
and bounded counters. It has no raw-payload input. The snapshot contains a
digest, counts and a short gateway observation; it excludes source, paths,
credentials, browser state, provider output and consent.

Human authority remains outside the adapter. The only advertised Companion
commands are a bounded human message and evidence-handoff export. The adapter
cannot accept a decision, create consent or execute an external system.

## Local proof

```powershell
python -m unittest discover -s tests -p "test_qcg_companion_adapter.py" -v
python -m fnpqnn_gateway_mvp --json gateway qcg-companion-snapshot `
  --session-id 21ce8a13-35d2-4b31-9eb0-a81af9629c64 `
  --view activity `
  --validated-contracts 4
```

The output is contract evidence only. A future application-specific content
bridge may carry this projection to a dedicated side panel, but that bridge
must retain the same allowlist and human-authority boundary.

The validation receipt is recorded in
[`reports/qcg_companion_gateway_adapter_2026-09-02.md`](../reports/qcg_companion_gateway_adapter_2026-09-02.md).
