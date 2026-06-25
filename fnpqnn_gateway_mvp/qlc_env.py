from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OPENCLAW_ENV = Path(os.getenv("OPENCLAW_WORKSPACE_ENV", Path.home() / ".openclaw" / "workspace" / ".env")).resolve()
DEFAULT_TOOL_ENV_KEYS = (
    "E2B_API_KEY",
    "DD_API_KEY",
    "DATADOG_API_KEY",
    "DD_DOGSTATSD_HOST",
    "DD_DOGSTATSD_PORT",
)


def qlc_tool_readiness(path: str | Path | None = None) -> dict[str, Any]:
    """Return redacted local readiness for QLC E2B/Datadog tooling."""

    env_load = load_openclaw_tool_env(path)
    presence = dict(env_load.get("presence") or {})
    dogstatsd_host_present = bool(presence.get("DD_DOGSTATSD_HOST") or os.environ.get("DD_DOGSTATSD_HOST"))
    dogstatsd_port_present = bool(presence.get("DD_DOGSTATSD_PORT") or os.environ.get("DD_DOGSTATSD_PORT"))
    return {
        "success": True,
        "schema": "ffed.qlc.tool_readiness_status.v1",
        "env_load": env_load,
        "e2b_key_present": bool(presence.get("E2B_API_KEY")),
        "datadog_key_present": bool(presence.get("DD_API_KEY") or presence.get("DATADOG_API_KEY")),
        "dogstatsd_config_present": dogstatsd_host_present and dogstatsd_port_present,
        "dogstatsd_reachable": "not_checked",
        "raw_values_printed": False,
    }


def load_openclaw_tool_env(
    path: str | Path | None = None,
    keys: Iterable[str] = DEFAULT_TOOL_ENV_KEYS,
) -> dict[str, Any]:
    env_path = Path(path).expanduser() if path else DEFAULT_OPENCLAW_ENV
    selected = tuple(dict.fromkeys(keys))
    loaded: list[str] = []
    if not env_path.exists():
        return {
            "success": False,
            "path": str(env_path),
            "loaded": loaded,
            "presence": {key: bool(os.environ.get(key)) for key in selected},
            "error": "env file not found",
            "raw_values_printed": False,
        }
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in selected:
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value
            loaded.append(key)
    return {
        "success": True,
        "path": str(env_path),
        "loaded": sorted(set(loaded)),
        "presence": {key: bool(os.environ.get(key)) for key in selected},
        "raw_values_printed": False,
    }
