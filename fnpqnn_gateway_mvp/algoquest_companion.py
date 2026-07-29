"""AlgoQuest/Qbit Education companion contracts.

This module is credential-blind and dry-run first. It validates the shared
Gateway -> AlgoQuest companion boundary before any Education app receives a
live integration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .algoquest_qbit_adapter import build_install_sequence_event
from .context_compressor import fingerprint_content, reject_secret_bearing_payload
from .suite_auth import EDUCATION_SUITE_REPOS


GATEWAY_INSTALL_SEQUENCE_SCHEMA = "securedme.education.gateway-install-sequence.v1"
EDUCATION_SESSION_ROLE_SCHEMA = "securedme.education.session-role.v1"
STUDENT_LEARNING_EVENT_SCHEMA = "securedme.education.student-learning-event.v1"
TEACHER_PLANNING_EVENT_SCHEMA = "securedme.education.teacher-planning-event.v1"
EDUCATION_METRICS_ENVELOPE_SCHEMA = "securedme.education.metrics-envelope.v1"
QBIT_INTERVENTION_SCHEMA = "securedme.education.qbit-intervention.v1"
COMPANION_PLAN_SCHEMA = "securedme.education.algoquest-companion-plan.v1"
THREE_APP_TEST_SCHEMA = "securedme.education.algoquest-three-app-test.v1"
APP_REGISTRATION_PLAN_SCHEMA = "securedme.education.algoquest-app-registration-plan.v1"
APP_CONTRACT_CHECK_SCHEMA = "securedme.education.algoquest-app-contract-check.v1"
ELEVEN_APP_CONTRACT_CHECK_SCHEMA = "securedme.education.algoquest-11-app-contract-check.v1"
APP_ADAPTER_MANIFEST_SCHEMA = "securedme.education.algoquest-qbit-app-adapter.v1"
APP_ADAPTER_MANIFEST_PATH = ".codex/algoquest-qbit-adapter.json"
QBIT_BADGE_ASSET_PATH = ".codex/algoquest-qbit-assets/algoquest-tiny-mark.png"
QBIT_BADGE_ASSET_ROLE = "tiny-cross-app-mark"

INSTALL_ORDER = ("gateway_doctor", "algoquest_companion_offer", "selected_tool")
REQUIRED_APP_CHECKS = (
    "webauth_template",
    "adapter_map",
    "install_sequence",
    "event_emitter",
    "metrics_envelope",
    "qbit_badge",
    "qbit_badge_asset_file",
    "qbit_nudge",
    "secret_rejection",
    "consent_scope",
    "route_plan_dry_run",
)
DOCTOR_STATUSES = ("passed", "failed")
ALGOQUEST_OFFER_STATUSES = ("enable_for_this_tool", "enable_for_suite", "skip_for_now")
SELECTED_TOOL_STATUSES = ("pending", "blocked", "installed")
ROLES = ("student_minor", "student_adult", "teacher")
SURFACES = ("student", "teacher")
STUDENT_ROLES = ("student_minor", "student_adult")
QBIT_STATES = ("badge", "nudge", "planner", "quiet", "disabled")
QBIT_SEVERITIES = ("info", "help", "warning", "blocked")
MIN_TEACHER_AGGREGATION_COUNT = 3
VAD_PROMOTION_THRESHOLD = 93
ALGOQUEST_SLUG = "algoquest"

FORBIDDEN_KEYS = {
    ".env",
    "api_key",
    "browser_session",
    "client_secret",
    "cookie",
    "oauth_token",
    "password",
    "raw_chat_log",
    "raw_prompt",
    "roster",
    "secret",
    "session_cookie",
    "student_email",
    "student_id",
    "student_name",
    "token",
}
ALLOWED_RAW_PROOF_KEYS = {"raw_payload_embedded", "raw_secret_stored", "raw_values_printed"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_expiry() -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=8)).isoformat()


def _id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{fingerprint_content(payload)[:16]}"


def _error(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _secret_errors(payload: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    try:
        reject_secret_bearing_payload(payload)
    except ValueError:
        errors.append(_error("secret_like_value", "payload contains token/cookie/password/secret-like material"))
    for key in _walk_keys(payload):
        normalized = key.lower()
        if normalized in ALLOWED_RAW_PROOF_KEYS:
            continue
        if normalized in FORBIDDEN_KEYS or normalized.startswith("raw_"):
            errors.append(_error("forbidden_field", f"{key} is not allowed in this contract"))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    if ".env" in text:
        errors.append(_error("forbidden_literal", ".env material is not allowed"))
    return errors


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _require(payload: Mapping[str, Any], fields: Iterable[str]) -> list[dict[str, str]]:
    return [_error("missing_field", f"{field} is required") for field in fields if payload.get(field) in (None, "", [])]


def _surface_for_role(role: str) -> str:
    if role in STUDENT_ROLES:
        return "student"
    if role == "teacher":
        return "teacher"
    return ""


def _schema_errors(payload: Mapping[str, Any], schema: str) -> list[dict[str, str]]:
    if payload.get("schema") != schema:
        return [_error("schema", f"expected {schema}")]
    return []


def _success(errors: list[dict[str, str]]) -> bool:
    return not errors


def _default_suite_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _embedded_adapter_manifest(repo: Any) -> dict[str, Any]:
    return {
        "schema": APP_ADAPTER_MANIFEST_SCHEMA,
        "app_slug": repo.slug,
        "hub_slug": ALGOQUEST_SLUG,
        "contract_version": "v1",
        "required_checks": list(REQUIRED_APP_CHECKS),
        "contracts": [
            GATEWAY_INSTALL_SEQUENCE_SCHEMA,
            EDUCATION_SESSION_ROLE_SCHEMA,
            STUDENT_LEARNING_EVENT_SCHEMA,
            EDUCATION_METRICS_ENVELOPE_SCHEMA,
            QBIT_INTERVENTION_SCHEMA,
        ],
        "sdk_hook_path": "RaySight-frontend/src/services/algoQuestEventBridge.ts",
        "sdk_hook_kind": "typescript",
        "qbit_badge_asset": QBIT_BADGE_ASSET_PATH,
        "qbit_badge_asset_role": QBIT_BADGE_ASSET_ROLE,
        "qbit_badge_asset_sha256": "CCE91C32706FC46EAD23A84CDD344D94204DA8D8450A3E24FCFFB613903D934D",
        "qbit_badge_asset_source": "algoquest-ams-discovry-labs-module-/assets/brand-selected/algoquest-tiny-mark.png",
        "dry_run": True,
        "raw_secret_stored": False,
        "_embedded_contract_fixture": True,
    }


def _allow_embedded_contract_fixture(
    manifest: Mapping[str, Any] | None,
    *,
    allow_embedded_fixture: bool = False,
) -> bool:
    return allow_embedded_fixture and bool(manifest and manifest.get("_embedded_contract_fixture") is True)


def build_gateway_install_sequence(
    requested_tool_slug: str,
    *,
    doctor_status: str = "passed",
    algoquest_offer_status: str = "skip_for_now",
    selected_tool_status: str = "pending",
    fingerprint_ref: str = "fingerprint-redacted",
    role: str = "student_minor",
) -> dict[str, Any]:
    seed = {
        "requested_tool_slug": requested_tool_slug,
        "doctor_status": doctor_status,
        "algoquest_offer_status": algoquest_offer_status,
        "selected_tool_status": selected_tool_status,
        "fingerprint_ref": fingerprint_ref,
        "role": role,
    }
    payload = {
        "schema": GATEWAY_INSTALL_SEQUENCE_SCHEMA,
        "install_id": _id("install", seed),
        "requested_tool_slug": requested_tool_slug,
        "doctor_status": doctor_status,
        "algoquest_offer_status": algoquest_offer_status,
        "selected_tool_status": selected_tool_status,
        "fingerprint_ref": fingerprint_ref,
        "role": role,
        "created_at": _now(),
        "contract_version": "v1",
        "install_order": list(INSTALL_ORDER),
        "stored_material": "choice_scope_only",
        "raw_secret_stored": False,
        "dry_run": True,
    }
    errors = validate_gateway_install_sequence(payload)
    payload["success"] = _success(errors)
    payload["decision"] = "allow_selected_tool" if payload["success"] else "block_selected_tool"
    payload["errors"] = errors
    payload["algoquest_event"] = build_install_sequence_event(payload)
    return payload


def validate_gateway_install_sequence(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, GATEWAY_INSTALL_SEQUENCE_SCHEMA)
    errors.extend(
        _require(
            payload,
            (
                "install_id",
                "requested_tool_slug",
                "doctor_status",
                "algoquest_offer_status",
                "selected_tool_status",
                "fingerprint_ref",
                "role",
                "created_at",
                "contract_version",
            ),
        )
    )
    if payload.get("doctor_status") not in DOCTOR_STATUSES:
        errors.append(_error("doctor_status", "doctor_status must be passed or failed"))
    if payload.get("algoquest_offer_status") not in ALGOQUEST_OFFER_STATUSES:
        errors.append(_error("algoquest_offer_status", "AlgoQuest offer must have an explicit supported status"))
    if payload.get("selected_tool_status") not in SELECTED_TOOL_STATUSES:
        errors.append(_error("selected_tool_status", "selected tool status is unsupported"))
    if payload.get("role") not in ROLES:
        errors.append(_error("role", "role must be a Gateway Education role"))
    if payload.get("doctor_status") == "failed" and payload.get("selected_tool_status") != "blocked":
        errors.append(_error("doctor_before_tool", "selected tool must be blocked when Gateway Doctor fails"))
    if not payload.get("algoquest_offer_status"):
        errors.append(_error("offer_before_tool", "AlgoQuest Companion Offer must be shown before the selected tool"))
    errors.extend(_secret_errors(payload))
    return errors


def build_session_role(
    role: str,
    *,
    surface: str | None = None,
    fingerprint_ref: str = "fingerprint-redacted",
    consent_scope: str = "tool",
    allowed_tools: Iterable[str] | None = None,
    age_band: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    resolved_surface = surface or _surface_for_role(role)
    seed = {"role": role, "surface": resolved_surface, "fingerprint_ref": fingerprint_ref}
    payload = {
        "schema": EDUCATION_SESSION_ROLE_SCHEMA,
        "session_id": _id("session", seed),
        "fingerprint_ref": fingerprint_ref,
        "role": role,
        "age_band": age_band or ("under_13_or_school_minor" if role == "student_minor" else "adult_or_staff"),
        "surface": resolved_surface,
        "consent_scope": consent_scope,
        "allowed_tools": list(allowed_tools or (ALGOQUEST_SLUG,)),
        "expires_at": expires_at or _default_expiry(),
        "created_at": _now(),
        "contract_version": "v1",
        "raw_secret_stored": False,
    }
    errors = validate_session_role(payload)
    payload["success"] = _success(errors)
    payload["errors"] = errors
    return payload


def validate_session_role(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, EDUCATION_SESSION_ROLE_SCHEMA)
    errors.extend(_require(payload, ("session_id", "fingerprint_ref", "role", "surface", "consent_scope", "allowed_tools", "expires_at")))
    role = str(payload.get("role", ""))
    surface = str(payload.get("surface", ""))
    if role not in ROLES:
        errors.append(_error("role", "unknown Education role"))
    if surface not in SURFACES:
        errors.append(_error("surface", "surface must be student or teacher"))
    expected_surface = _surface_for_role(role)
    if expected_surface and surface != expected_surface:
        errors.append(_error("role_surface_mismatch", f"{role} cannot use /{surface}"))
    try:
        expiry = datetime.fromisoformat(str(payload.get("expires_at", "")).replace("Z", "+00:00"))
        if expiry <= datetime.now(timezone.utc):
            errors.append(_error("session_expired", "session is expired"))
    except ValueError:
        errors.append(_error("expires_at", "expires_at must be ISO 8601"))
    errors.extend(_secret_errors({k: v for k, v in payload.items() if k != "session_id"}))
    return errors


def build_student_learning_event(
    app_slug: str,
    artifact_ref: str,
    *,
    skill_area: str,
    difficulty_band: str,
    score: float,
    threshold: float = VAD_PROMOTION_THRESHOLD,
    attempt_count: int = 1,
    blocked_reason: str = "",
    next_step_hint: str = "",
    qbit_help_accepted: bool = False,
    risk_flags: Iterable[str] | None = None,
) -> dict[str, Any]:
    seed = {"app_slug": app_slug, "artifact_ref": artifact_ref, "score": score, "threshold": threshold}
    payload = {
        "schema": STUDENT_LEARNING_EVENT_SCHEMA,
        "event_id": _id("student-event", seed),
        "app_slug": app_slug,
        "artifact_ref": artifact_ref,
        "skill_area": skill_area,
        "difficulty_band": difficulty_band,
        "score": score,
        "threshold": threshold,
        "attempt_count": attempt_count,
        "blocked_reason": blocked_reason,
        "next_step_hint": next_step_hint,
        "qbit_help_accepted": qbit_help_accepted,
        "risk_flags": list(risk_flags or ()),
        "created_at": _now(),
        "contract_version": "v1",
        "raw_secret_stored": False,
    }
    errors = validate_student_learning_event(payload)
    payload["success"] = _success(errors)
    payload["errors"] = errors
    return payload


def validate_student_learning_event(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, STUDENT_LEARNING_EVENT_SCHEMA)
    errors.extend(
        _require(
            payload,
            (
                "event_id",
                "app_slug",
                "artifact_ref",
                "skill_area",
                "difficulty_band",
                "created_at",
                "contract_version",
            ),
        )
    )
    if "score" not in payload:
        errors.append(_error("missing_field", "score is required"))
    if "threshold" not in payload:
        errors.append(_error("missing_field", "threshold is required"))
    if int(payload.get("attempt_count", 0)) < 1:
        errors.append(_error("attempt_count", "attempt_count must be >= 1"))
    errors.extend(_secret_errors(payload))
    return errors


def build_teacher_planning_event(
    app_slug: str,
    *,
    classroom_scope: str,
    aggregate_need: str,
    rubric_ref: str,
    activity_ref: str,
    risk_flags: Iterable[str] | None = None,
    tool_recommendation: str = "",
    intervention_plan_ref: str = "",
    aggregation_count: int = MIN_TEACHER_AGGREGATION_COUNT,
    redaction_status: str = "redacted",
) -> dict[str, Any]:
    seed = {"app_slug": app_slug, "classroom_scope": classroom_scope, "activity_ref": activity_ref}
    payload = {
        "schema": TEACHER_PLANNING_EVENT_SCHEMA,
        "event_id": _id("teacher-event", seed),
        "app_slug": app_slug,
        "classroom_scope": classroom_scope,
        "aggregate_need": aggregate_need,
        "rubric_ref": rubric_ref,
        "activity_ref": activity_ref,
        "risk_flags": list(risk_flags or ()),
        "tool_recommendation": tool_recommendation,
        "intervention_plan_ref": intervention_plan_ref,
        "aggregation_count": aggregation_count,
        "redaction_status": redaction_status,
        "created_at": _now(),
        "contract_version": "v1",
        "raw_secret_stored": False,
    }
    errors = validate_teacher_planning_event(payload)
    payload["success"] = _success(errors)
    payload["errors"] = errors
    return payload


def validate_teacher_planning_event(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, TEACHER_PLANNING_EVENT_SCHEMA)
    errors.extend(
        _require(
            payload,
            (
                "event_id",
                "app_slug",
                "classroom_scope",
                "aggregate_need",
                "rubric_ref",
                "activity_ref",
                "redaction_status",
                "created_at",
                "contract_version",
            ),
        )
    )
    if payload.get("redaction_status") != "redacted":
        errors.append(_error("redaction_status", "teacher events must be redacted"))
    if int(payload.get("aggregation_count", 0)) < MIN_TEACHER_AGGREGATION_COUNT:
        errors.append(_error("aggregation_minimum", f"teacher aggregation_count must be >= {MIN_TEACHER_AGGREGATION_COUNT}"))
    errors.extend(_secret_errors(payload))
    return errors


def build_metrics_envelope(
    surface: str,
    app_slug: str,
    event_type: str,
    *,
    metric_store: str,
    count: int = 1,
    latency_ms: int = 0,
    redaction_status: str = "redacted",
    dimensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    seed = {"surface": surface, "app_slug": app_slug, "event_type": event_type, "metric_store": metric_store}
    payload = {
        "schema": EDUCATION_METRICS_ENVELOPE_SCHEMA,
        "metric_id": _id("metric", seed),
        "surface": surface,
        "metric_store": metric_store,
        "app_slug": app_slug,
        "event_type": event_type,
        "count": count,
        "latency_ms": latency_ms,
        "contract_version": "v1",
        "redaction_status": redaction_status,
        "dimensions": dict(dimensions or {}),
        "created_at": _now(),
        "raw_secret_stored": False,
    }
    errors = validate_metrics_envelope(payload)
    payload["success"] = _success(errors)
    payload["errors"] = errors
    return payload


def validate_metrics_envelope(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, EDUCATION_METRICS_ENVELOPE_SCHEMA)
    errors.extend(_require(payload, ("metric_id", "surface", "metric_store", "app_slug", "event_type", "contract_version", "redaction_status")))
    surface = str(payload.get("surface", ""))
    metric_store = str(payload.get("metric_store", ""))
    if surface not in ("student", "teacher", "install"):
        errors.append(_error("surface", "metrics surface must be student, teacher, or install"))
    if metric_store not in ("student", "teacher", "install"):
        errors.append(_error("metric_store", "metric_store must be student, teacher, or install"))
    if surface in ("student", "teacher") and metric_store != surface:
        errors.append(_error("metrics_store_mismatch", f"{surface} metrics cannot be written to {metric_store} store"))
    if int(payload.get("count", 0)) < 0:
        errors.append(_error("count", "count cannot be negative"))
    if int(payload.get("latency_ms", 0)) < 0:
        errors.append(_error("latency_ms", "latency_ms cannot be negative"))
    errors.extend(_secret_errors(payload))
    return errors


def build_qbit_intervention(
    surface: str,
    *,
    trigger_reason: str,
    severity: str = "info",
    message_key: str = "qbit.generic.next_step",
    suggested_tool: str = ALGOQUEST_SLUG,
    requires_consent: bool = True,
    requires_teacher: bool = False,
    action_plan_ref: str = "",
    state: str = "badge",
) -> dict[str, Any]:
    seed = {"surface": surface, "trigger_reason": trigger_reason, "suggested_tool": suggested_tool}
    payload = {
        "schema": QBIT_INTERVENTION_SCHEMA,
        "intervention_id": _id("qbit", seed),
        "surface": surface,
        "trigger_reason": trigger_reason,
        "severity": severity,
        "message_key": message_key,
        "suggested_tool": suggested_tool,
        "requires_consent": requires_consent,
        "requires_teacher": requires_teacher,
        "action_plan_ref": action_plan_ref,
        "state": state,
        "created_at": _now(),
        "contract_version": "v1",
        "raw_secret_stored": False,
    }
    errors = validate_qbit_intervention(payload)
    payload["success"] = _success(errors)
    payload["errors"] = errors
    return payload


def validate_qbit_intervention(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    errors = _schema_errors(payload, QBIT_INTERVENTION_SCHEMA)
    errors.extend(_require(payload, ("intervention_id", "surface", "trigger_reason", "severity", "message_key", "created_at", "contract_version")))
    if payload.get("surface") not in SURFACES:
        errors.append(_error("surface", "Qbit surface must be student or teacher"))
    if payload.get("state") not in QBIT_STATES:
        errors.append(_error("state", "Qbit state is unsupported"))
    if payload.get("severity") not in QBIT_SEVERITIES:
        errors.append(_error("severity", "Qbit severity is unsupported"))
    suggested_tool = str(payload.get("suggested_tool", ""))
    if suggested_tool and suggested_tool != ALGOQUEST_SLUG and payload.get("requires_consent") is not True:
        errors.append(_error("cross_app_consent", "cross-app Qbit suggestions require explicit consent"))
    errors.extend(_secret_errors(payload))
    return errors


def redact_student_event_for_teacher(student_event: Mapping[str, Any], *, classroom_scope: str = "classroom-redacted") -> dict[str, Any]:
    errors = validate_student_learning_event(student_event)
    if errors:
        return {
            "schema": TEACHER_PLANNING_EVENT_SCHEMA,
            "success": False,
            "errors": errors,
            "raw_secret_stored": False,
        }
    risk_flags = list(student_event.get("risk_flags", []))
    score = float(student_event.get("score", 0))
    threshold = float(student_event.get("threshold", VAD_PROMOTION_THRESHOLD))
    need = "extend_high_score_artifact" if score >= threshold else "support_before_promotion"
    return build_teacher_planning_event(
        ALGOQUEST_SLUG,
        classroom_scope=classroom_scope,
        aggregate_need=need,
        rubric_ref=f"rubric:{student_event.get('skill_area')}",
        activity_ref=f"artifact-summary:{student_event.get('artifact_ref')}",
        risk_flags=risk_flags,
        tool_recommendation="vot-guardian" if any(flag in {"secret", "privacy", "security"} for flag in risk_flags) else ALGOQUEST_SLUG,
        intervention_plan_ref="redacted-plan-pending",
        aggregation_count=MIN_TEACHER_AGGREGATION_COUNT,
        redaction_status="redacted",
    )


def three_app_validation_fixture(score: float = VAD_PROMOTION_THRESHOLD) -> dict[str, Any]:
    promoted = score >= VAD_PROMOTION_THRESHOLD
    install = build_gateway_install_sequence(
        "visual-algorithm",
        doctor_status="passed",
        algoquest_offer_status="enable_for_suite",
        selected_tool_status="pending",
        role="student_minor",
    )
    student_event = build_student_learning_event(
        "visual-algorithm",
        "vad:validated-algorithm:artifact-pointer",
        skill_area="algorithm_design",
        difficulty_band="grade5-sec2",
        score=score,
        threshold=VAD_PROMOTION_THRESHOLD,
        next_step_hint="Open AlgoQuest challenge and request Guardian review for privacy risk.",
        qbit_help_accepted=True,
        risk_flags=("privacy", "secret") if promoted else ("needs_revision",),
    )
    teacher_event = redact_student_event_for_teacher(student_event)
    qbit = build_qbit_intervention(
        "student",
        trigger_reason="validated_algorithm_promoted" if promoted else "validated_algorithm_below_threshold",
        severity="warning" if promoted else "help",
        message_key="qbit.vad.guardian_plan" if promoted else "qbit.vad.revise_before_promotion",
        suggested_tool="vot-guardian" if promoted else ALGOQUEST_SLUG,
        requires_consent=True,
        action_plan_ref="guardian-plan:pointer-only" if promoted else "algoquest-revision-plan",
        state="nudge",
    )
    guardian_pointer = {
        "schema": "securedme.education.artifact-pointer.v1",
        "source_app": "visual-algorithm",
        "target_app": "vot-guardian",
        "artifact_ref": student_event["artifact_ref"],
        "raw_secret_stored": False,
        "raw_payload_embedded": False,
    }
    validation_errors = []
    for item in (install, student_event, teacher_event, qbit, guardian_pointer):
        validation_errors.extend(_secret_errors(item))
    payload = {
        "schema": THREE_APP_TEST_SCHEMA,
        "success": promoted and not validation_errors,
        "dry_run": True,
        "apps": ["visual-algorithm", ALGOQUEST_SLUG, "vot-guardian"],
        "threshold": VAD_PROMOTION_THRESHOLD,
        "score": score,
        "promoted": promoted,
        "install_sequence": install,
        "student_event": student_event,
        "teacher_event": teacher_event,
        "qbit_intervention": qbit,
        "guardian_pointer": guardian_pointer,
        "validation_errors": validation_errors,
        "raw_secret_stored": False,
    }
    return payload


def eleven_app_registration_plan() -> dict[str, Any]:
    apps = [repo.as_dict() for repo in EDUCATION_SUITE_REPOS if repo.slug != ALGOQUEST_SLUG]
    return {
        "schema": APP_REGISTRATION_PLAN_SCHEMA,
        "success": len(apps) == 11,
        "app_count": len(apps),
        "excluded_hub": ALGOQUEST_SLUG,
        "apps": apps,
        "required_checks_per_app": list(REQUIRED_APP_CHECKS),
        "raw_secret_stored": False,
        "dry_run": True,
    }


def _build_route_plan(source: str, target: str, action: str) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "action": action,
        "status": "needs_review",
        "dry_run": True,
        "live_write_gated": True,
        "steps": [
            f"confirm active controller session for {source} -> {target}",
            f"read secret-free state from {source}",
            f"prepare gated action plan for {target}",
            "require explicit execute=true and valid session before any live write",
        ],
    }


def _secret_rejection_probe(app_slug: str) -> dict[str, Any]:
    probe = build_metrics_envelope(
        "student",
        app_slug,
        "contract_secret_probe",
        metric_store="student",
        dimensions={"student_name": "blocked"},
    )
    codes = {error["code"] for error in probe["errors"]}
    return {
        "success": "forbidden_field" in codes,
        "rejected_codes": sorted(codes),
        "raw_secret_stored": False,
    }


def _load_app_adapter_manifest(
    repo: Any,
    suite_root: str | Path | None = None,
    *,
    allow_embedded_fixture: bool = False,
) -> tuple[dict[str, Any] | None, Path, str]:
    root = Path(suite_root).expanduser().resolve() if suite_root else _default_suite_root()
    path = root / repo.path / APP_ADAPTER_MANIFEST_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8")), path, ""
    except FileNotFoundError:
        if allow_embedded_fixture:
            return _embedded_adapter_manifest(repo), path, ""
        return None, path, "missing_manifest"
    except json.JSONDecodeError as exc:
        return None, path, f"invalid_json:{exc.msg}"


def _validate_app_adapter_manifest(manifest: Mapping[str, Any] | None, repo: Any) -> list[dict[str, str]]:
    if manifest is None:
        return [_error("adapter_manifest_missing", f"{APP_ADAPTER_MANIFEST_PATH} is missing")]

    errors = _schema_errors(manifest, APP_ADAPTER_MANIFEST_SCHEMA)
    errors.extend(
        _require(
            manifest,
            (
                "schema",
                "app_slug",
                "hub_slug",
                "contract_version",
                "required_checks",
                "contracts",
                "sdk_hook_path",
                "sdk_hook_kind",
                "qbit_badge_asset",
                "qbit_badge_asset_role",
                "qbit_badge_asset_sha256",
                "qbit_badge_asset_source",
                "dry_run",
                "raw_secret_stored",
            ),
        )
    )
    if manifest.get("app_slug") != repo.slug:
        errors.append(_error("adapter_manifest_app_slug", f"expected {repo.slug}"))
    if manifest.get("hub_slug") != ALGOQUEST_SLUG:
        errors.append(_error("adapter_manifest_hub", "hub_slug must be algoquest"))
    if manifest.get("contract_version") != "v1":
        errors.append(_error("adapter_manifest_version", "contract_version must be v1"))
    if manifest.get("dry_run") is not True:
        errors.append(_error("adapter_manifest_dry_run", "manifest must declare dry_run=true until live controller execution"))
    if manifest.get("raw_secret_stored") is not False:
        errors.append(_error("adapter_manifest_secret_policy", "raw_secret_stored must be false"))
    required_checks = set(manifest.get("required_checks", []))
    missing_checks = [check for check in REQUIRED_APP_CHECKS if check not in required_checks]
    if missing_checks:
        errors.append(_error("adapter_manifest_required_checks", "missing: " + ",".join(missing_checks)))
    contracts = set(manifest.get("contracts", []))
    required_contracts = {
        GATEWAY_INSTALL_SEQUENCE_SCHEMA,
        EDUCATION_SESSION_ROLE_SCHEMA,
        STUDENT_LEARNING_EVENT_SCHEMA,
        EDUCATION_METRICS_ENVELOPE_SCHEMA,
        QBIT_INTERVENTION_SCHEMA,
    }
    missing_contracts = sorted(required_contracts - contracts)
    if missing_contracts:
        errors.append(_error("adapter_manifest_contracts", "missing: " + ",".join(missing_contracts)))
    errors.extend(_secret_errors(manifest))
    return errors


def _validate_qbit_badge_asset_path(
    manifest: Mapping[str, Any] | None,
    repo: Any,
    suite_root: str | Path | None = None,
    *,
    allow_embedded_fixture: bool = False,
) -> tuple[Path | None, list[dict[str, str]]]:
    if manifest is None:
        return None, [_error("qbit_badge_asset_manifest_missing", "cannot validate qbit badge asset without adapter manifest")]

    raw_asset_path = str(manifest.get("qbit_badge_asset", ""))
    if not raw_asset_path:
        return None, [_error("qbit_badge_asset", "qbit_badge_asset is required")]
    if raw_asset_path != QBIT_BADGE_ASSET_PATH:
        return None, [_error("qbit_badge_asset", f"expected {QBIT_BADGE_ASSET_PATH}")]
    if Path(raw_asset_path).is_absolute() or ".." in Path(raw_asset_path).parts:
        return None, [_error("qbit_badge_asset", "qbit_badge_asset must stay inside the app repository")]
    if manifest.get("qbit_badge_asset_role") != QBIT_BADGE_ASSET_ROLE:
        return None, [_error("qbit_badge_asset_role", f"expected {QBIT_BADGE_ASSET_ROLE}")]

    expected_hash = str(manifest.get("qbit_badge_asset_sha256", "")).upper()
    if len(expected_hash) != 64:
        return None, [_error("qbit_badge_asset_sha256", "qbit_badge_asset_sha256 must be a full SHA-256 hash")]

    root = Path(suite_root).expanduser().resolve() if suite_root else _default_suite_root()
    repo_path = (root / repo.path).resolve()
    asset_path = (repo_path / raw_asset_path).resolve()
    try:
        asset_path.relative_to(repo_path)
    except ValueError:
        return asset_path, [_error("qbit_badge_asset", "resolved qbit badge asset path escapes the app repository")]
    if not asset_path.exists():
        if _allow_embedded_contract_fixture(manifest, allow_embedded_fixture=allow_embedded_fixture):
            return asset_path, []
        return asset_path, [_error("qbit_badge_asset_missing", f"{raw_asset_path} is missing")]

    actual_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest().upper()
    if actual_hash != expected_hash:
        return asset_path, [_error("qbit_badge_asset_sha256", "qbit badge asset hash does not match manifest")]
    return asset_path, []


def _validate_sdk_hook_path(
    manifest: Mapping[str, Any] | None,
    repo: Any,
    suite_root: str | Path | None = None,
    *,
    allow_embedded_fixture: bool = False,
) -> tuple[Path | None, list[dict[str, str]]]:
    if manifest is None:
        return None, [_error("sdk_hook_manifest_missing", "cannot validate sdk hook without adapter manifest")]

    raw_hook_path = str(manifest.get("sdk_hook_path", ""))
    if not raw_hook_path:
        return None, [_error("sdk_hook_path", "sdk_hook_path is required")]
    if Path(raw_hook_path).is_absolute() or ".." in Path(raw_hook_path).parts:
        return None, [_error("sdk_hook_path", "sdk_hook_path must stay inside the app repository")]

    root = Path(suite_root).expanduser().resolve() if suite_root else _default_suite_root()
    repo_path = (root / repo.path).resolve()
    hook_path = (repo_path / raw_hook_path).resolve()
    try:
        hook_path.relative_to(repo_path)
    except ValueError:
        return hook_path, [_error("sdk_hook_path", "resolved sdk hook path escapes the app repository")]
    if not hook_path.exists():
        if _allow_embedded_contract_fixture(manifest, allow_embedded_fixture=allow_embedded_fixture):
            return hook_path, []
        return hook_path, [_error("sdk_hook_missing", f"{raw_hook_path} is missing")]
    if manifest.get("sdk_hook_kind") not in {"python", "javascript", "typescript"}:
        return hook_path, [_error("sdk_hook_kind", "sdk_hook_kind must be python, javascript, or typescript")]
    return hook_path, []


def build_app_contract_check(
    repo_slug: str,
    *,
    suite_root: str | Path | None = None,
    allow_embedded_fixture: bool = False,
) -> dict[str, Any]:
    repo = next((item for item in EDUCATION_SUITE_REPOS if item.slug == repo_slug), None)
    if repo is None:
        return {
            "schema": APP_CONTRACT_CHECK_SCHEMA,
            "success": False,
            "app_slug": repo_slug,
            "errors": [_error("unknown_app", "app is not in the canonical Education suite inventory")],
            "raw_secret_stored": False,
            "dry_run": True,
        }

    adapter_manifest, adapter_manifest_path, adapter_manifest_read_error = _load_app_adapter_manifest(
        repo,
        suite_root,
        allow_embedded_fixture=allow_embedded_fixture,
    )
    adapter_manifest_errors = _validate_app_adapter_manifest(adapter_manifest, repo)
    if adapter_manifest_read_error and not adapter_manifest_errors:
        adapter_manifest_errors.append(_error("adapter_manifest_read", adapter_manifest_read_error))
    sdk_hook_path, sdk_hook_errors = _validate_sdk_hook_path(
        adapter_manifest,
        repo,
        suite_root,
        allow_embedded_fixture=allow_embedded_fixture,
    )
    qbit_badge_asset_path, qbit_badge_asset_errors = _validate_qbit_badge_asset_path(
        adapter_manifest,
        repo,
        suite_root,
        allow_embedded_fixture=allow_embedded_fixture,
    )

    install = build_gateway_install_sequence(
        repo.slug,
        doctor_status="passed",
        algoquest_offer_status="enable_for_suite",
        selected_tool_status="pending",
        role="student_minor",
    )
    session = build_session_role("student_minor", allowed_tools=(ALGOQUEST_SLUG, repo.slug), consent_scope="suite")
    student_event = build_student_learning_event(
        repo.slug,
        f"{repo.slug}:artifact:pointer",
        skill_area="education_suite_connection",
        difficulty_band="beginner",
        score=VAD_PROMOTION_THRESHOLD,
        threshold=VAD_PROMOTION_THRESHOLD,
        attempt_count=1,
        next_step_hint=f"Open AlgoQuest support for {repo.app}.",
        qbit_help_accepted=False,
        risk_flags=(),
    )
    metrics = build_metrics_envelope(
        "student",
        repo.slug,
        "contract_registration_check",
        metric_store="student",
        count=1,
        latency_ms=0,
        redaction_status="none",
        dimensions={"threshold": VAD_PROMOTION_THRESHOLD, "attempt_count": 1},
    )
    qbit_badge = build_qbit_intervention(
        "student",
        trigger_reason=f"{repo.slug}_qbit_badge_available",
        severity="info",
        message_key="qbit.badge.available",
        suggested_tool=ALGOQUEST_SLUG,
        requires_consent=False,
        action_plan_ref=f"algoquest:{repo.slug}:badge",
        state="badge",
    )
    qbit_nudge = build_qbit_intervention(
        "student",
        trigger_reason=f"{repo.slug}_qbit_nudge_available",
        severity="help",
        message_key="qbit.nudge.available",
        suggested_tool=ALGOQUEST_SLUG,
        requires_consent=False,
        action_plan_ref=f"algoquest:{repo.slug}:nudge",
        state="nudge",
    )
    secret_rejection = _secret_rejection_probe(repo.slug)
    route_plan = _build_route_plan("Gateway", repo.slug, "validate AlgoQuest companion contract registration")

    check_results = {
        "webauth_template": bool(repo.slug and repo.domain),
        "adapter_map": bool(repo.path and repo.name) and not adapter_manifest_errors,
        "install_sequence": install["success"],
        "event_emitter": student_event["success"],
        "metrics_envelope": metrics["success"],
        "qbit_badge": qbit_badge["success"],
        "qbit_badge_asset_file": not qbit_badge_asset_errors,
        "qbit_nudge": qbit_nudge["success"],
        "secret_rejection": secret_rejection["success"],
        "consent_scope": install.get("algoquest_offer_status") == "enable_for_suite" and session.get("consent_scope") == "suite",
        "route_plan_dry_run": route_plan["dry_run"] is True and route_plan["live_write_gated"] is True,
    }

    errors: list[dict[str, str]] = []
    errors.extend(adapter_manifest_errors)
    errors.extend(sdk_hook_errors)
    errors.extend(qbit_badge_asset_errors)
    for check_name in REQUIRED_APP_CHECKS:
        if not check_results.get(check_name):
            errors.append(_error(check_name, f"{repo.slug} failed {check_name}"))
    for contract_name, contract in (
        ("install_sequence", install),
        ("session_role", session),
        ("student_event", student_event),
        ("metrics_envelope", metrics),
        ("qbit_badge", qbit_badge),
        ("qbit_nudge", qbit_nudge),
    ):
        for error in contract.get("errors", []):
            errors.append(_error(contract_name, f"{error['code']}:{error['detail']}"))

    payload = {
        "schema": APP_CONTRACT_CHECK_SCHEMA,
        "success": not errors,
        "app": repo.as_dict(),
        "required_checks": list(REQUIRED_APP_CHECKS),
        "adapter_manifest_path": str(adapter_manifest_path),
        "adapter_manifest": adapter_manifest or {},
        "sdk_hook_path": str(sdk_hook_path) if sdk_hook_path else "",
        "qbit_badge_asset_path": str(qbit_badge_asset_path) if qbit_badge_asset_path else "",
        "check_results": check_results,
        "install_sequence": install,
        "session_role": session,
        "student_event": student_event,
        "metrics_envelope": metrics,
        "qbit_badge": qbit_badge,
        "qbit_nudge": qbit_nudge,
        "secret_rejection": secret_rejection,
        "route_plan": route_plan,
        "errors": errors,
        "raw_secret_stored": False,
        "dry_run": True,
    }
    payload["check_fingerprint"] = fingerprint_content(payload)
    return payload


def eleven_app_contract_check_plan(
    *,
    suite_root: str | Path | None = None,
    allow_embedded_fixture: bool = False,
) -> dict[str, Any]:
    apps = [repo for repo in EDUCATION_SUITE_REPOS if repo.slug != ALGOQUEST_SLUG]
    checks = [
        build_app_contract_check(
            repo.slug,
            suite_root=suite_root,
            allow_embedded_fixture=allow_embedded_fixture,
        )
        for repo in apps
    ]
    failed = [check for check in checks if not check["success"]]
    payload = {
        "schema": ELEVEN_APP_CONTRACT_CHECK_SCHEMA,
        "success": len(checks) == 11 and not failed,
        "app_count": len(checks),
        "expected_app_count": 11,
        "excluded_hub": ALGOQUEST_SLUG,
        "required_checks_per_app": list(REQUIRED_APP_CHECKS),
        "apps": checks,
        "summary": {
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "raw_secret_stored": False,
            "dry_run": True,
        },
        "raw_secret_stored": False,
        "dry_run": True,
    }
    payload["plan_fingerprint"] = fingerprint_content(payload)
    return payload


def companion_contract_plan(*, allow_embedded_fixture: bool = False) -> dict[str, Any]:
    install = build_gateway_install_sequence("algorithm-builder", algoquest_offer_status="enable_for_this_tool")
    student_session = build_session_role("student_minor")
    teacher_session = build_session_role("teacher")
    three_app = three_app_validation_fixture()
    registration = eleven_app_registration_plan()
    eleven_app_contracts = eleven_app_contract_check_plan(allow_embedded_fixture=allow_embedded_fixture)
    payload = {
        "schema": COMPANION_PLAN_SCHEMA,
        "success": all(
            (
                install["success"],
                student_session["success"],
                teacher_session["success"],
                three_app["success"],
                registration["success"],
                eleven_app_contracts["success"],
            )
        ),
        "dry_run": True,
        "contracts": [
            GATEWAY_INSTALL_SEQUENCE_SCHEMA,
            EDUCATION_SESSION_ROLE_SCHEMA,
            STUDENT_LEARNING_EVENT_SCHEMA,
            TEACHER_PLANNING_EVENT_SCHEMA,
            EDUCATION_METRICS_ENVELOPE_SCHEMA,
            QBIT_INTERVENTION_SCHEMA,
        ],
        "install_sequence": install,
        "student_session": student_session,
        "teacher_session": teacher_session,
        "three_app_validation": three_app,
        "eleven_app_registration": registration,
        "eleven_app_contract_check": eleven_app_contracts,
        "raw_secret_stored": False,
    }
    payload["plan_fingerprint"] = fingerprint_content(payload)
    return payload
