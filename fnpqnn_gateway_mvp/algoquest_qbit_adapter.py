"""Gateway-side AlgoQuest/Qbit Education adapter hook."""

from __future__ import annotations

import hashlib

APP_SLUG = "gateway"
HUB_SLUG = "algoquest"
EVENT_SCHEMA = "securedme.education.student-learning-event.v1"
OUTBOX_KEY = "securedme.education.algoquest.outbox.v1"


def build_learning_event_stub(artifact_ref: str, *, score: float = 93) -> dict:
    return build_learning_event(artifact_ref, score=score)


def build_learning_event(artifact_ref: str, *, score: float = 93, workflow: str = "gateway_install_sequence") -> dict:
    if not artifact_ref or not artifact_ref.startswith(f"{APP_SLUG}:"):
        raise ValueError("artifact_ref must be a gateway artifact pointer")
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    return {
        "schema": EVENT_SCHEMA,
        "app_slug": APP_SLUG,
        "artifact_ref": artifact_ref,
        "skill_area": "gateway_install_sequence",
        "difficulty_band": "operator",
        "score": score,
        "threshold": 93,
        "attempt_count": 1,
        "blocked_reason": "",
        "next_step_hint": "Confirm Gateway Doctor before routing the selected Education tool.",
        "qbit_help_accepted": False,
        "risk_flags": [],
        "contract_version": "v1",
        "raw_secret_stored": False,
        "dry_run": True,
        "workflow": workflow,
        "outbox_key": OUTBOX_KEY,
    }


def build_install_sequence_event(install_sequence: dict) -> dict:
    install_id = install_sequence.get("install_id")
    requested_tool_slug = install_sequence.get("requested_tool_slug")
    if not isinstance(install_id, str) or not install_id.strip():
        raise ValueError("install_sequence must contain install_id")
    if not isinstance(requested_tool_slug, str) or not requested_tool_slug.strip():
        raise ValueError("install_sequence must contain requested_tool_slug")
    event = build_learning_event(
        f"{APP_SLUG}:install:{_stable_ref(install_id)}",
        workflow="gateway_doctor_algoquest_offer",
    )
    event["requested_tool_ref"] = f"tool:{_stable_ref(requested_tool_slug)}"
    event["install_order"] = list(install_sequence.get("install_order", ()))
    event["offer_status"] = install_sequence.get("algoquest_offer_status")
    event["doctor_status"] = install_sequence.get("doctor_status")
    event["selected_tool_status"] = install_sequence.get("selected_tool_status")
    return event


def _stable_ref(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]
