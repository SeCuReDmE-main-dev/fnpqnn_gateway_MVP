"""Secret-safe context compression and artifact pointers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .token_budget import TOKEN_GOVERNOR_DIR
from .token_estimator import estimate_tokens


COMPRESSION_SCHEMA = "securedme.token_governor.compression_receipt.v1"
ARTIFACT_SCHEMA = "securedme.token_governor.artifact_pointer.v1"
NEUTROSOPHIC_KEYS = ("T", "I", "F", "dF", "D_f", "i_fractal", "I_system^S", "I_system_S")
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|oauth|cookie|session|password|secret)\s*[:=]\s*['\"]?[^'\"\s,}]+"),
    re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint_content(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def sanitize_visible_content(content: Any) -> Any:
    if isinstance(content, dict):
        return {str(key): sanitize_visible_content(value) for key, value in content.items()}
    if isinstance(content, list):
        return [sanitize_visible_content(item) for item in content]
    if isinstance(content, str):
        cleaned = content
        for pattern in SECRET_PATTERNS:
            cleaned = pattern.sub("<redacted-secret>", cleaned)
        return cleaned
    return content


def reject_secret_bearing_payload(content: Any) -> None:
    text = _stable_json(content)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("token governor rejected a secret-bearing payload")


def preserve_math_symbols_and_neutrosophic_fields(content: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    if isinstance(content, dict):
        for key, value in content.items():
            if str(key) in NEUTROSOPHIC_KEYS:
                found[str(key)] = value
            nested = preserve_math_symbols_and_neutrosophic_fields(value)
            found.update({k: v for k, v in nested.items() if k not in found})
    elif isinstance(content, list):
        for item in content:
            nested = preserve_math_symbols_and_neutrosophic_fields(item)
            found.update({k: v for k, v in nested.items() if k not in found})
    elif isinstance(content, str):
        for key in NEUTROSOPHIC_KEYS:
            if key in content and key not in found:
                found[key] = "present-in-text"
    return found


def make_artifact_pointer(content: Any, metadata: dict[str, Any] | None = None, *, workspace: str | Path = ".", write: bool = False) -> dict[str, Any]:
    reject_secret_bearing_payload(content)
    safe_content = sanitize_visible_content(content)
    digest = fingerprint_content(safe_content)
    path = Path(workspace).expanduser().resolve() / TOKEN_GOVERNOR_DIR / "artifacts" / f"{digest}.json"
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(_stable_json({"schema": ARTIFACT_SCHEMA, "metadata": metadata or {}, "content": safe_content}), encoding="utf-8")
    return {
        "schema": ARTIFACT_SCHEMA,
        "artifact_id": digest[:16],
        "sha256": digest,
        "path": str(path),
        "written": bool(write and path.exists()),
        "metadata": metadata or {},
        "raw_content_included": False,
    }


def _summarize_item(item: Any, max_chars: int) -> str:
    text = _stable_json(sanitize_visible_content(item))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 24] + "...<compacted>"


def compress_context(
    history: Any,
    budget: dict[str, Any],
    *,
    provider: str,
    workspace: str | Path = ".",
    write: bool = False,
) -> dict[str, Any]:
    safe_history = sanitize_visible_content(history)
    reject_secret_bearing_payload(history)
    items = safe_history if isinstance(safe_history, list) else [safe_history]
    max_items = int(budget.get("max_history_items", 6))
    retained = items[-max_items:]
    compacted_count = max(0, len(items) - len(retained))
    max_chars_each = max(160, int(budget.get("max_visible_chars", 2400)) // max(1, len(retained)))
    summaries = [_summarize_item(item, max_chars_each) for item in retained]
    snapshot = {
        "retained_summaries": summaries,
        "neutrosophic_fields": preserve_math_symbols_and_neutrosophic_fields(safe_history),
        "compacted_items": compacted_count,
    }
    estimate_before = estimate_tokens(safe_history, provider=provider)
    estimate_after = estimate_tokens(snapshot, provider=provider)
    pointer = make_artifact_pointer(safe_history, {"kind": "pre_compaction_history"}, workspace=workspace, write=write)
    before = max(1, int(estimate_before["estimated_tokens"]))
    after = int(estimate_after["estimated_tokens"])
    return {
        "schema": COMPRESSION_SCHEMA,
        "success": True,
        "created_at": _now(),
        "provider": provider,
        "budget": budget,
        "snapshot": snapshot,
        "artifact_pointer": pointer,
        "token_usage": {
            "before": estimate_before,
            "after": estimate_after,
            "compression_ratio": round(after / before, 4),
        },
        "raw_secret_stored": False,
        "dry_run": not write,
    }
