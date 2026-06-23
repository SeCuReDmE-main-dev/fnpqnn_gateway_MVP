"""Obsidian-style persistent RAG bridge for gateway memory.

The bridge creates inspectable Markdown notes and a JSONL index. Native tools
can use their own memory systems, but only explicit exports/admissions are
written here. This keeps provider memory and gateway memory connected without
merging or scraping private stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .activation import route_for_tool


DEFAULT_VAULT_DIR = ".fnpqnn_gateway/obsidian_vault"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "note"


def _vault_path(workspace: str | Path = ".", vault: str | Path | None = None) -> Path:
    ws = Path(workspace).expanduser().resolve()
    raw = Path(vault) if vault else Path(DEFAULT_VAULT_DIR)
    return raw.expanduser().resolve() if raw.is_absolute() else (ws / raw).resolve()


def _paths(vault_path: Path) -> dict[str, str]:
    return {
        "vault": str(vault_path),
        "index": str(vault_path / "gateway_rag_index.jsonl"),
        "home": str(vault_path / "Gateway RAG Home.md"),
        "routes": str(vault_path / "Routes"),
        "notes": str(vault_path / "Notes"),
        "admissions": str(vault_path / "Admissions"),
    }


def obsidian_plan(tool: str, workspace: str | Path = ".", vault: str | Path | None = None) -> dict[str, Any]:
    route = route_for_tool(tool)
    vault_path = _vault_path(workspace, vault)
    return {
        "success": True,
        "tool": route.tool,
        "runtime_hook": route.runtime_hook,
        "vault_semantics": "obsidian-markdown-jsonl-rag",
        "paths": _paths(vault_path),
        "frontmatter_schema": {
            "fnpqnn_tool": route.tool,
            "runtime_hook": route.runtime_hook,
            "source": "native-tool-export|gateway-note|simulator-event",
            "tags": ["fnpqnn", route.tool, "gateway-rag"],
            "created_at": "ISO-8601",
        },
        "memory_contract": {
            "native_memory_is_owner": True,
            "gateway_memory_is_admitted_copy": True,
            "raw_tokens_allowed": False,
            "private_tool_store_scraping": False,
            "rag_surface": "Markdown notes plus gateway_rag_index.jsonl",
        },
        "lvfm_stream_contract": {
            "metaphor": "obsidian creek feeds the main LVFM river",
            "target_layer": "FNP-QNN LVFMRuntimeGraph via Cerebrum runtime",
            "gateway_role": "prepare admitted note events only",
            "simulator_ingest_endpoint": "POST /cerebrum/runtime/ingest",
            "simulator_run_endpoint": "POST /cerebrum/runtime/run",
            "no_import_boundary": True,
        },
    }


def init_obsidian(tool: str, workspace: str | Path = ".", vault: str | Path | None = None, write: bool = False, force: bool = False) -> dict[str, Any]:
    plan = obsidian_plan(tool, workspace, vault)
    plan["dry_run"] = not write
    if not write:
        return plan
    paths = {key: Path(value) for key, value in plan["paths"].items()}
    for key in ("vault", "routes", "notes", "admissions"):
        paths[key].mkdir(parents=True, exist_ok=True)
    home = paths["home"]
    route_note = paths["routes"] / f"{plan['tool']}.md"
    documents = {
        home: (
            "# FNP-QNN Gateway RAG Home\n\n"
            "This vault is the persistent, inspectable bridge between native tool memory and gateway memory.\n\n"
            "## Rules\n\n"
            "- Native tools keep their own private memory.\n"
            "- Only explicit exports/admissions are written here.\n"
            "- Do not store raw tokens or provider secrets.\n"
            "- Use notes and `gateway_rag_index.jsonl` as the shared retrieval surface.\n"
        ),
        route_note: (
            f"# Route: {plan['tool']}\n\n"
            f"- runtime_hook: {plan['runtime_hook']}\n"
            "- bridge: non-absorbing native tool to FNP-QNN gateway memory\n\n"
            "## Use\n\n"
            "Native agents can read this vault to recover simulator context, gate decisions, onboarding answers, and admitted memories.\n"
        ),
    }
    written: list[str] = []
    skipped: list[str] = []
    for path, content in documents.items():
        if path.exists() and not force:
            skipped.append(str(path))
            continue
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    paths["index"].touch(exist_ok=True)
    plan["written"] = written
    plan["skipped_existing"] = skipped
    return plan


def record_note(
    tool: str,
    title: str,
    content: str,
    workspace: str | Path = ".",
    vault: str | Path | None = None,
    tags: list[str] | None = None,
    source: str = "gateway-note",
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    route = route_for_tool(tool)
    vault_path = _vault_path(workspace, vault)
    paths = _paths(vault_path)
    note_dir = Path(paths["notes"])
    note_path = note_dir / f"{_slug(title)}.md"
    note_tags = ["fnpqnn", route.tool, "gateway-rag", *(tags or [])]
    created = _now()
    note = (
        "---\n"
        f"fnpqnn_tool: {route.tool}\n"
        f"runtime_hook: {route.runtime_hook}\n"
        f"source: {source}\n"
        f"created_at: {created}\n"
        "tags:\n"
        + "".join(f"  - {tag}\n" for tag in note_tags)
        + "---\n\n"
        f"# {title}\n\n"
        f"{content.strip()}\n"
    )
    payload: dict[str, Any] = {
        "success": True,
        "dry_run": not write,
        "tool": route.tool,
        "title": title,
        "path": str(note_path),
        "index": paths["index"],
        "tags": note_tags,
        "source": source,
        "created_at": created,
        "lvfm_stream": {
            "enabled": True,
            "stream": "obsidian-admission-creek",
            "target_layer": "lvfm-runtime-river",
            "cerebrum_candidate": True,
        },
    }
    if not write:
        payload["markdown_preview"] = note
        return payload
    note_dir.mkdir(parents=True, exist_ok=True)
    if note_path.exists() and not force:
        payload["success"] = False
        payload["blocked_reason"] = "Note exists; pass --force to overwrite."
        return payload
    note_path.write_text(note, encoding="utf-8")
    index_path = Path(paths["index"])
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({key: payload[key] for key in ("tool", "title", "path", "tags", "source", "created_at", "lvfm_stream")}, sort_keys=True) + "\n")
    return payload


def query_notes(query: str, workspace: str | Path = ".", vault: str | Path | None = None, limit: int = 5) -> dict[str, Any]:
    vault_path = _vault_path(workspace, vault)
    index_path = vault_path / "gateway_rag_index.jsonl"
    terms = [term.lower() for term in re.findall(r"[a-zA-Z0-9_]+", query)]
    results: list[dict[str, Any]] = []
    if not index_path.exists():
        return {"success": True, "query": query, "results": [], "index": str(index_path)}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        path = Path(item["path"])
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        haystack = (item.get("title", "") + " " + " ".join(item.get("tags", [])) + " " + text).lower()
        score = sum(haystack.count(term) for term in terms) if terms else 0
        if score > 0:
            item["score"] = score
            results.append(item)
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"success": True, "query": query, "results": results[:limit], "index": str(index_path)}


def lvfm_stream(query: str, workspace: str | Path = ".", vault: str | Path | None = None, limit: int = 5) -> dict[str, Any]:
    """Build a Cerebrum/LVFM candidate stream from admitted Obsidian notes."""

    retrieved = query_notes(query, workspace, vault, limit)
    events: list[dict[str, Any]] = []
    for item in retrieved["results"]:
        path = Path(item["path"])
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        events.append(
            {
                "source": f"obsidian://{path.name}",
                "text": content,
                "metadata": {
                    "title": item.get("title"),
                    "tool": item.get("tool"),
                    "tags": item.get("tags", []),
                    "admission_source": item.get("source"),
                    "target_layer": "LVFMRuntimeGraph",
                    "bridge": "obsidian-creek-to-lvfm-river",
                },
                "lvfm_hint": {
                    "T": "preserve confirmed/admitted content",
                    "I": "track ambiguity and missing context",
                    "dF": "preserve differentiated uncertainty separately from generic I",
                    "F": "track contradiction, stale context, or rejection risk",
                },
            }
        )
    return {
        "success": True,
        "query": query,
        "stream": "obsidian-admission-creek",
        "target_layer": "lvfm-runtime-river",
        "cerebrum_ingest_endpoint": "POST /cerebrum/runtime/ingest",
        "cerebrum_run_endpoint": "POST /cerebrum/runtime/run",
        "cerebrum_payload": {"memories": events},
        "events": events,
        "source_index": retrieved["index"],
    }
