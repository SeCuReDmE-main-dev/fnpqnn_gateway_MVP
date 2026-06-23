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
