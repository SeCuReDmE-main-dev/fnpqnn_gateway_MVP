"""Cloud kit integration plans for external data ingestion.

E2B is treated as an optional isolated compute lane. The gateway can prepare
plans and handoff files for external data normalization, then admit summaries
into the Obsidian creek that feeds the LVFM river.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Any

from .activation import route_for_tool


DEFAULT_OPENCLAW_ENV = Path(os.getenv("OPENCLAW_WORKSPACE_ENV", Path.home() / ".openclaw" / "workspace" / ".env")).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "external-data"


def e2b_status() -> dict[str, Any]:
    return {
        "success": True,
        "provider": "e2b",
        "packages": {
            "e2b": importlib.util.find_spec("e2b") is not None,
            "e2b_code_interpreter": importlib.util.find_spec("e2b_code_interpreter") is not None,
        },
        "env_present": {"E2B_API_KEY": bool(os.environ.get("E2B_API_KEY"))},
        "raw_token_stored": False,
        "role": "optional isolated compute lane for external data normalization",
        "official_flow": [
            "create sandbox",
            "upload input data or fetch approved source",
            "run normalization/inspection code",
            "download or emit sanitized summary",
            "admit summary into Obsidian RAG",
            "stream admitted note into LVFM",
        ],
    }


def load_env_file(path: str | Path | None = None, keys: tuple[str, ...] = ("E2B_API_KEY",)) -> dict[str, Any]:
    env_path = Path(path).expanduser() if path else DEFAULT_OPENCLAW_ENV
    loaded: list[str] = []
    if not env_path.exists():
        return {"success": False, "path": str(env_path), "loaded": loaded, "error": "env file not found"}
    selected = set(keys)
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


def e2b_smoke(env_file: str | Path | None = None) -> dict[str, Any]:
    env_load = load_env_file(env_file)
    if not os.environ.get("E2B_API_KEY"):
        return {
            "success": False,
            "provider": "e2b",
            "env_load": env_load,
            "error": "E2B_API_KEY is missing or empty",
            "raw_token_stored": False,
        }
    try:
        from e2b import Sandbox
    except Exception as exc:
        error_msg = str(exc)
        api_key = os.environ.get("E2B_API_KEY")
        if api_key and api_key in error_msg:
            error_msg = error_msg.replace(api_key, "[REDACTED_API_KEY]")
        return {
            "success": False,
            "provider": "e2b",
            "env_load": env_load,
            "error": f"e2b package unavailable: {type(exc).__name__}: {error_msg}",
            "raw_token_stored": False,
        }
    try:
        with Sandbox.create() as sandbox:
            result = sandbox.commands.run("python - <<'PY'\nprint('fnpqnn-gateway-e2b-smoke-ok')\nPY")
            sandbox_id = getattr(sandbox, "sandbox_id", None)
        stdout = str(getattr(result, "stdout", ""))
        return {
            "success": "fnpqnn-gateway-e2b-smoke-ok" in stdout,
            "provider": "e2b",
            "sandbox_id": sandbox_id,
            "stdout_contains_expected_marker": "fnpqnn-gateway-e2b-smoke-ok" in stdout,
            "raw_token_stored": False,
        }
    except Exception as exc:
        error_msg = str(exc)
        api_key = os.environ.get("E2B_API_KEY")
        if api_key and api_key in error_msg:
            error_msg = error_msg.replace(api_key, "[REDACTED_API_KEY]")
        return {
            "success": False,
            "provider": "e2b",
            "env_load": env_load,
            "error": f"{type(exc).__name__}: {error_msg}",
            "raw_token_stored": False,
        }


def e2b_ingest_plan(
    tool: str,
    source: str,
    title: str,
    workspace: str | Path = ".",
    vault: str | Path | None = None,
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    route = route_for_tool(tool)
    ws = Path(workspace).expanduser().resolve()
    cloud_dir = ws / ".fnpqnn_gateway" / "cloud_kit" / "e2b"
    slug = _slug(title)
    plan_path = cloud_dir / f"{slug}.json"
    prompt_path = cloud_dir / f"{slug}.md"
    vault_arg = [] if vault is None else ["--vault", str(vault)]
    record_command = [
        "fnpqnn",
        "memory",
        "obsidian-record",
        "--tool",
        route.tool,
        "--title",
        title,
        "--content",
        "<sanitized E2B result summary>",
        "--tag",
        "e2b",
        "--tag",
        "external-data",
        "--tag",
        "lvfm",
        "--write",
        *vault_arg,
    ]
    lvfm_command = [
        "fnpqnn",
        "memory",
        "obsidian-lvfm-stream",
        "--query",
        title,
        *vault_arg,
    ]
    payload: dict[str, Any] = {
        "success": True,
        "dry_run": not write,
        "created_at": _now(),
        "tool": route.tool,
        "runtime_hook": route.runtime_hook,
        "source": source,
        "title": title,
        "paths": {"plan": str(plan_path), "prompt": str(prompt_path)},
        "e2b_status": e2b_status(),
        "pipeline": [
            "external source approved by user",
            "E2B sandbox normalizes or inspects data",
            "sanitized result admitted to Obsidian RAG",
            "Obsidian creek feeds LVFM stream",
            "simulator owns Cerebrum/LVFM ingestion",
        ],
        "commands": {
            "admit_to_obsidian": record_command,
            "feed_lvfm": lvfm_command,
        },
        "boundaries": {
            "no_raw_tokens": True,
            "no_private_tool_memory_scrape": True,
            "no_unapproved_source_fetch": True,
            "sandbox_required_for_untrusted_code": True,
            "gateway_does_not_import_simulator": True,
        },
    }
    markdown = (
        f"# E2B External Data Ingest Plan: {title}\n\n"
        f"- source: {source}\n"
        f"- native tool: {route.tool}\n"
        f"- runtime hook: {route.runtime_hook}\n\n"
        "## Pipeline\n\n"
        + "\n".join(f"- {step}" for step in payload["pipeline"])
        + "\n\n## Admission Command\n\n```powershell\n"
        + " ".join(record_command)
        + "\n```\n\n## LVFM Stream Command\n\n```powershell\n"
        + " ".join(lvfm_command)
        + "\n```\n"
    )
    payload["markdown_preview"] = markdown
    if write:
        cloud_dir.mkdir(parents=True, exist_ok=True)
        for path, content in ((plan_path, json.dumps(payload, indent=2, sort_keys=True)), (prompt_path, markdown)):
            if path.exists() and not force:
                continue
            path.write_text(content, encoding="utf-8")
    return payload
