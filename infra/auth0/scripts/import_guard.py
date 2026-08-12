"""Run a non-destructive Auth0 import only after a fresh passing preflight."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


root = Path(__file__).parents[1]
preflight = root / "snapshots" / "preflight.json"
if os.environ.get("SECUREDME_AUTH0_IMPORT_CONFIRMATION") != "IMPORT_DEVELOPMENT_SYNTHETIC_TENANT":
    raise SystemExit("import blocked: explicit development-tenant confirmation missing")
if os.environ.get("AUTH0_ALLOW_DELETE", "false").lower() != "false":
    raise SystemExit("import blocked: AUTH0_ALLOW_DELETE must be false")
if not preflight.exists() or time.time() - preflight.stat().st_mtime > 900:
    raise SystemExit("import blocked: passing preflight must be less than 15 minutes old")
if not json.loads(preflight.read_text(encoding="utf-8")).get("safe_to_dry_run"):
    raise SystemExit("import blocked: preflight did not approve this tenant")
command = [str(root / "node_modules" / ".bin" / "a0deploy.cmd"), "import", "-c", "config.json",
           "--input_file", "tenant.yaml", "--dry-run", "--apply"]
raise SystemExit(subprocess.call(command, cwd=root, shell=False))
