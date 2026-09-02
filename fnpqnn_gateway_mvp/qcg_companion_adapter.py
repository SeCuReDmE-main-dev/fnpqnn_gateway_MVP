"""Bounded QCG Companion snapshot producer for the FNP-QNN gateway.

This adapter proves that the gateway can project a small, provider-neutral
evidence view into the public QCG Companion contract. It does not read runtime
configuration, execute a provider, grant consent, or expose a raw gateway
payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from .context_compressor import fingerprint_content


ADAPTER_SCHEMA = "securedme.gateway.qcg-companion-adapter.v1"
QCG_SNAPSHOT_SCHEMA = "qcg-console-snapshot.v2"
QCG_VIEWS = (
    "inspector",
    "console",
    "webmcp",
    "decisions",
    "sources",
    "receipts",
    "activity",
)
GATEWAY_STATES = ("ready", "degraded", "blocked")
MAX_COUNTER = 1_000_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _bounded_counter(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_COUNTER:
        raise ValueError(f"{name} must be an integer between 0 and {MAX_COUNTER}")
    return value


def _session_id(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("session_id must be a UUID") from exc


def _enum(value: str, allowed: tuple[str, ...], name: str) -> str:
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return _utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("created_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("created_at must be a timezone-aware ISO-8601 timestamp")
    return parsed.replace(microsecond=0).isoformat()


def build_qcg_companion_snapshot(
    *,
    session_id: str,
    view: str = "inspector",
    gateway_state: str = "ready",
    validated_contracts: int = 0,
    evidence_exports: int = 0,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a strict, source-free QCG side-panel snapshot envelope.

    Only enum values and bounded counters enter the projection. The adapter
    therefore has no parameter through which a token, provider response, local
    path, raw source, browser state, or ``.env`` value could cross the boundary.
    """

    safe_session = _session_id(session_id)
    safe_view = _enum(view, QCG_VIEWS, "view")
    safe_state = _enum(gateway_state, GATEWAY_STATES, "gateway_state")
    contract_count = _bounded_counter(validated_contracts, "validated_contracts")
    export_count = _bounded_counter(evidence_exports, "evidence_exports")
    timestamp = _timestamp(created_at)

    bounded_state = {
        "adapter_schema": ADAPTER_SCHEMA,
        "gateway_state": safe_state,
        "selected_view": safe_view,
        "validated_contracts": contract_count,
        "evidence_exports": export_count,
    }
    digest = fingerprint_content(bounded_state)
    event_id = str(uuid5(NAMESPACE_URL, f"{ADAPTER_SCHEMA}:{safe_session}:{digest}"))
    phase = {"ready": "active", "degraded": "recovery", "blocked": "error"}[safe_state]
    authority_state = "ready" if safe_state == "ready" else "unavailable"

    snapshot = {
        "schema_version": QCG_SNAPSHOT_SCHEMA,
        "surface": "sidepanel",
        "session_id": safe_session,
        "phase": phase,
        "authority_state": authority_state,
        "artifact": {
            "id": f"gateway-{digest[:16]}",
            "digest": digest,
            "format": "gateway-event",
            "profile": "fnpqnn-gateway",
            "compiler_status": "validated" if safe_state == "ready" else safe_state,
        },
        "effects": {
            "inspections": 1,
            "evaluations": 0,
            "local_simulations": 0,
            "metadata_validations": contract_count,
            "qpu_submissions": 0,
            "evidence_exports": export_count,
        },
        "storage_mode": "memory",
        "available_commands": ["human_message", "export_debug_handoff"],
        "invocations": [
            {
                "tool": "read_debug_context",
                "status": "completed",
                "timestamp": timestamp,
                "summary": "Gateway metadata projected through a bounded local adapter.",
            }
        ],
        "collaboration": {
            "participants": [
                {"actor": "fnpqnn-gateway", "role": "sanitized-snapshot-producer"}
            ],
            "messages": [
                {
                    "event_id": event_id,
                    "actor": "fnpqnn-gateway",
                    "role": "sanitized-snapshot-producer",
                    "kind": "observation",
                    "summary": f"Gateway state is {safe_state}; human authority remains external.",
                    "status": "open",
                    "issued_at": timestamp,
                }
            ],
            "open_reviews": 0,
            "memory_tombstones": [],
        },
        "tools": [
            {"name": "read_debug_context", "group": "collaboration", "status": "registered"},
            {"name": "post_debug_message", "group": "collaboration", "status": "registered"},
            {"name": "request_human_review", "group": "collaboration", "status": "registered"},
            {"name": "export_debug_handoff", "group": "collaboration", "status": "registered"},
        ],
    }
    return {
        "schema": ADAPTER_SCHEMA,
        "success": True,
        "dry_run": True,
        "selected_view": safe_view,
        "navigation": {"selected": safe_view, "available": list(QCG_VIEWS)},
        "qcg_snapshot": snapshot,
        "boundary": {
            "raw_gateway_payload_included": False,
            "raw_source_included": False,
            "provider_state_included": False,
            "credentials_included": False,
            "consent_created": False,
            "external_execution": False,
        },
        "adapter_fingerprint": digest,
    }


def navigate_qcg_companion(envelope: dict[str, Any], view: str) -> dict[str, Any]:
    """Rebuild the bounded projection with another allowed local view."""

    if envelope.get("schema") != ADAPTER_SCHEMA or not isinstance(envelope.get("qcg_snapshot"), dict):
        raise ValueError("unsupported QCG Companion gateway envelope")
    snapshot = envelope["qcg_snapshot"]
    effects = snapshot.get("effects", {})
    state = {
        "active": "ready",
        "recovery": "degraded",
        "error": "blocked",
    }.get(snapshot.get("phase"))
    if state is None:
        raise ValueError("unsupported gateway phase")
    return build_qcg_companion_snapshot(
        session_id=snapshot.get("session_id", ""),
        view=view,
        gateway_state=state,
        validated_contracts=effects.get("metadata_validations", 0),
        evidence_exports=effects.get("evidence_exports", 0),
        created_at=snapshot.get("invocations", [{}])[0].get("timestamp"),
    )
