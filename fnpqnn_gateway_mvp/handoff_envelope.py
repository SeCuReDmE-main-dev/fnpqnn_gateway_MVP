"""Model-visible handoff envelopes for native tools."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .context_compressor import make_artifact_pointer, preserve_math_symbols_and_neutrosophic_fields, reject_secret_bearing_payload, sanitize_visible_content
from .token_budget import resolve_budget
from .token_estimator import estimate_tokens


HANDOFF_SCHEMA = "securedme.token_governor.handoff_envelope.v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    import json

    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compact(value: Any, max_chars: int) -> str:
    text = _text(value)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 24)] + "...<artifact-pointer>"


def build_handoff_envelope(
    payload: Any,
    *,
    route: str,
    activity: str,
    user_profile: str,
    policy: dict[str, Any] | None = None,
    workspace: str | Path = ".",
    write_artifacts: bool = False,
) -> dict[str, Any]:
    budget = resolve_budget(route=route, activity=activity, user_profile=user_profile, policy=policy)
    provider = str(budget["provider"])
    reject_secret_bearing_payload(payload)
    safe_payload = sanitize_visible_content(payload)
    pointer = make_artifact_pointer(
        safe_payload,
        {"route": route, "activity": activity, "user_profile": user_profile},
        workspace=workspace,
        write=write_artifacts,
    )
    max_visible_chars = int(budget["max_visible_chars"])
    stable_context = [
        "Official school providers are Codex/OpenAI and Antigravity/Gemini only.",
        "Keep provider secrets, cookies, browser sessions, and dotenv values out of model-visible content.",
        "Preserve I -> I_system^S -> D_f -> dF -> i_fractal in math and simulator summaries.",
    ]
    visible = {
        "schema": HANDOFF_SCHEMA,
        "route": route,
        "activity": activity,
        "user_profile": user_profile,
        "stable_context": stable_context,
        "selected_context": _compact(safe_payload, max_visible_chars),
        "artifact_pointers": [pointer],
        "neutrosophic_fields": preserve_math_symbols_and_neutrosophic_fields(safe_payload),
        "next_actions": [
            "Use the visible summary first.",
            "Request a specific artifact only when the current task requires it.",
            "Keep tool results compact and cite artifact ids instead of dumping raw state.",
        ],
    }
    token_usage = estimate_tokens(visible, provider=provider)
    return {
        "schema": HANDOFF_SCHEMA,
        "success": int(token_usage["estimated_tokens"]) <= int(budget["max_input_tokens"]),
        "created_at": _now(),
        "budget": budget,
        "visible": visible,
        "_meta": {
            "hidden_from_model_contract": True,
            "artifact_ids": [pointer["artifact_id"]],
            "raw_content_included": False,
        },
        "token_usage": token_usage,
        "quality_score": score_context_quality({"visible": visible, "budget": budget, "token_usage": token_usage}),
        "raw_secret_stored": False,
        "dry_run": not write_artifacts,
    }


def score_context_quality(envelope: dict[str, Any]) -> dict[str, Any]:
    visible = envelope.get("visible", {})
    budget = envelope.get("budget", {})
    usage = envelope.get("token_usage", {})
    score = 100
    checks = {
        "has_stable_context": bool(visible.get("stable_context")),
        "has_artifact_pointer": bool(visible.get("artifact_pointers")),
        "has_next_actions": bool(visible.get("next_actions")),
        "preserves_neutrosophic_fields": "neutrosophic_fields" in visible,
        "within_budget": int(usage.get("estimated_tokens", 0)) <= int(budget.get("max_input_tokens", 1)),
    }
    for passed in checks.values():
        if not passed:
            score -= 15
    return {"score": max(0, score), "checks": checks}
