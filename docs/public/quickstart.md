# FNP-QNN Gateway quickstart

## Requirements

Use a clean checkout, the runtime declared by the repository, and its committed lockfiles. Confirm the active branch before installing anything.

```powershell
git status --short --branch
```

Inspect the shared Education authentication policy without writing state:

```powershell
python -m fnpqnn_gateway_mvp --json gateway suite-auth-audit --root "Z:\SecuredMe Education suite"
```

Treat the result as adapter-contract evidence only. Test live login separately in every deployed application.

## Install

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## Start

```powershell
.venv\Scripts\fnpqnn-gateway --help
.venv\Scripts\fnpqnn-gateway-mcp
```

## Verify

```powershell
.venv\Scripts\python -m pytest
```

## Human acceptance

Inspect the output, logs, test results, and diff. Accept, request a correction, quarantine, or stop; do not silently promote a generated result.
