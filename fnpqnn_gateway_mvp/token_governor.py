"""SecuredMe Token Governor orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .context_compressor import compress_context, reject_secret_bearing_payload, sanitize_visible_content
from .handoff_envelope import build_handoff_envelope
from .telemetry import emit_gateway_submit_counter
from .token_budget import TOKEN_GOVERNOR_DIR, default_policy, resolve_budget
from .token_estimator import estimate_tokens


GOVERNOR_PLAN_SCHEMA = "securedme.token_governor.plan.v1"
GOVERNOR_CHECK_SCHEMA = "securedme.token_governor.check.v1"
REPORT_NAME = "TOKEN_GOVERNOR_IMPLEMENTATION_REPORT.md"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def token_governor_dir(workspace: str | Path) -> Path:
    return _workspace_path(workspace) / TOKEN_GOVERNOR_DIR


def policy_path(workspace: str | Path, preset: str) -> Path:
    suffix = "default" if preset == "classroom" else preset
    return token_governor_dir(workspace) / f"policy.{suffix}.json"


def classify_activity(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower() if not isinstance(payload, str) else payload.lower()
    if any(term in text for term in ("teacher", "review", "rubric", "classroom")):
        return "teacher_review"
    if any(term in text for term in ("research", "citation", "source", "deepsearch", "web search")):
        return "research"
    if any(term in text for term in ("traceback", "bug", "exception", "debug", "pytest", "stack")):
        return "debug"
    if any(term in text for term in ("proof", "theorem", "lemma", "d_f", "df", "i_fractal", "∑", "∀")):
        return "math_proof"
    if any(term in text for term in ("simulation", "simulator", "qnn", "lvfm", "cerebrum", "epoch")):
        return "simulation"
    return "short_question"


def _load_policy(workspace: str | Path, preset: str) -> dict[str, Any]:
    path = policy_path(workspace, preset)
    base = default_policy(preset)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        merged = {**base, **loaded}
        for key in ("activity_profiles", "user_profiles", "route_budgets", "rules"):
            if key not in loaded:
                merged[key] = base[key]
        return merged
    return base


def _write_policy_files(workspace: str | Path, *, force: bool = False) -> list[str]:
    written: list[str] = []
    for preset in ("classroom", "operator"):
        path = policy_path(workspace, preset)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            continue
        path.write_text(json.dumps(default_policy(preset), indent=2, sort_keys=True), encoding="utf-8")
        written.append(str(path))
    return written


def token_governor_plan(
    *,
    route: str,
    payload: Any,
    workspace: str | Path = ".",
    activity: str | None = None,
    user_profile: str | None = None,
    preset: str = "classroom",
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    policy = _load_policy(workspace, preset)
    selected_activity = activity or classify_activity(payload)
    selected_user = user_profile or str(policy["default_user_profile"])
    budget = resolve_budget(route=route, activity=selected_activity, user_profile=selected_user, policy=policy)
    envelope = build_handoff_envelope(
        payload,
        route=route,
        activity=selected_activity,
        user_profile=selected_user,
        policy=policy,
        workspace=workspace,
        write_artifacts=write,
    )
    provider = str(budget["provider"])
    cache_candidate = estimate_tokens(envelope["visible"]["stable_context"], provider=provider)
    metrics = {
        "input_tokens_est": envelope["token_usage"]["estimated_tokens"],
        "output_visible_tokens_est": estimate_tokens(envelope["visible"], provider=provider)["estimated_tokens"],
        "cache_candidate_prefix_tokens": cache_candidate["estimated_tokens"],
        "cache_hit_tokens": None,
        "route": route,
        "activity": selected_activity,
    }
    written = _write_policy_files(workspace, force=force) if write else []
    if write:
        plan_path = token_governor_dir(workspace) / "last_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps({"envelope": envelope, "metrics": metrics}, indent=2, sort_keys=True), encoding="utf-8")
        written.append(str(plan_path))
    return {
        "schema": GOVERNOR_PLAN_SCHEMA,
        "success": envelope["success"],
        "created_at": _now(),
        "route": route,
        "activity": selected_activity,
        "user_profile": selected_user,
        "budget": budget,
        "envelope": envelope,
        "metrics": metrics,
        "paths": {
            "policy_default": str(policy_path(workspace, "classroom")),
            "policy_operator": str(policy_path(workspace, "operator")),
            "last_plan": str(token_governor_dir(workspace) / "last_plan.json"),
        },
        "written": written,
        "raw_secret_stored": False,
        "dry_run": not write,
    }


def token_governor_check(
    payload: Any,
    *,
    route: str,
    workspace: str | Path = ".",
    activity: str | None = None,
    user_profile: str | None = None,
    preset: str = "classroom",
    emit_metrics: bool = False,
) -> dict[str, Any]:
    secret_safe = True
    error = ""
    try:
        reject_secret_bearing_payload(payload)
    except ValueError as exc:
        secret_safe = False
        error = str(exc)
    safe_payload = sanitize_visible_content(payload)
    plan = token_governor_plan(
        route=route,
        payload=safe_payload,
        workspace=workspace,
        activity=activity,
        user_profile=user_profile,
        preset=preset,
        write=False,
    ) if secret_safe else None
    checks = {
        "secret_safe": secret_safe,
        "within_budget": bool(plan and plan["success"]),
        "raw_secret_stored": False,
        "dry_run_available": True,
        "preserves_neutrosophic_fields": bool(plan and "neutrosophic_fields" in plan["envelope"]["visible"]),
    }
    success = (
        checks["secret_safe"]
        and checks["within_budget"]
        and checks["dry_run_available"]
        and checks["preserves_neutrosophic_fields"]
        and not checks["raw_secret_stored"]
    )
    if emit_metrics and plan:
        emit_gateway_submit_counter(
            "token_governor_check",
            (
                f"route:{route}",
                f"activity:{plan['activity']}",
                f"within_budget:{str(checks['within_budget']).lower()}",
            ),
        )
    return {
        "schema": GOVERNOR_CHECK_SCHEMA,
        "success": success,
        "checks": checks,
        "error": error,
        "plan": plan,
        "raw_secret_stored": False,
    }


def token_governor_compress(
    history: Any,
    *,
    route: str,
    workspace: str | Path = ".",
    activity: str | None = None,
    user_profile: str | None = None,
    preset: str = "classroom",
    write: bool = False,
) -> dict[str, Any]:
    selected_policy = _load_policy(workspace, preset)
    selected_activity = activity or classify_activity(history)
    selected_user = user_profile or str(selected_policy["default_user_profile"])
    budget = resolve_budget(route=route, activity=selected_activity, user_profile=selected_user, policy=selected_policy)
    return compress_context(history, budget, provider=str(budget["provider"]), workspace=workspace, write=write)


def implementation_report(workspace: str | Path = ".") -> dict[str, Any]:
    report_path = _workspace_path(workspace) / "docs" / REPORT_NAME
    return {
        "success": report_path.exists(),
        "path": str(report_path),
        "status": "pre-alpha",
        "report": report_path.read_text(encoding="utf-8") if report_path.exists() else "",
    }
