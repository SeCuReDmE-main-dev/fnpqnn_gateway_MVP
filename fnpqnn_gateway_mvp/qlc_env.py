from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable
from .telemetry import local_metrics_endpoint


DEFAULT_OPENCLAW_ENV = Path(os.getenv("OPENCLAW_WORKSPACE_ENV", Path.home() / ".openclaw" / "workspace" / ".env")).resolve()
DEFAULT_TOOL_ENV_KEYS = (
    "E2B_API_KEY",
    "SECUREDME_OTEL_ENABLED",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
)


def qlc_tool_readiness(path: str | Path | None = None) -> dict[str, Any]:
    """Return redacted readiness; no telemetry connection is attempted."""

    env_load = load_openclaw_tool_env(path)
    presence = dict(env_load.get("presence") or {})
    return {
        "success": True,
        "schema": "ffed.qlc.tool_readiness_status.v1",
        "env_load": env_load,
        "e2b_key_present": bool(presence.get("E2B_API_KEY")),
        "otel_enabled": os.environ.get("SECUREDME_OTEL_ENABLED", "").lower() == "true",
        "otel_endpoint_allowed": local_metrics_endpoint(os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://127.0.0.1:4318/v1/metrics")),
        "otel_reachable": "not_checked",
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
