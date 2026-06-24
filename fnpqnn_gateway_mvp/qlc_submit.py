"""QLC workflow bundle submission to the FNP-QNN simulator boundary."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence
from urllib import request
from urllib.error import HTTPError, URLError


WORKFLOW_SCHEMA = "ffed.qlc.protection_workflow_bundle.v1"
GATEWAY_SUBMISSION_SCHEMA = "ffed.qlc.gateway_submission.v1"
LOOP_RECEIPT_SCHEMA = "ffed.qlc.gateway_celebrum_loop_receipt.v1"
RUNTIME_PATH = "/cerebrum/runtime/run"

FORBIDDEN_QCL_SUBMISSION_FIELDS = {
    "api_key",
    "authorization",
    "browsing_history",
    "credential",
    "full_activity_dump",
    "image_bytes",
    "ocr_text",
    "password",
    "private_key",
    "raw_activity",
    "raw_browsing_history",
    "raw_image",
    "raw_ocr",
    "raw_payload",
    "raw_secret",
    "screenshot",
    "screenshots",
    "secret",
    "token",
    "video_bytes",
}


def qlc_submit(
    qlc_bundle: Mapping[str, Any],
    *,
    simulator_url: str = "http://localhost:8000",
    dry_run: bool = False,
    timeout: int = 30,
    e2b_enabled: bool = False,
) -> dict[str, Any]:
    """Validate a QLC bundle and optionally submit its mesh payload to Cerebrum."""

    submission = extract_gateway_submission(qlc_bundle)
    runtime_payload = _mapping(submission.get("mesh_payload"))
    runtime_fingerprint = _fingerprint(runtime_payload)
    route_action = str(submission.get("route_action") or "submit_to_cerebrum")
    endpoint = _runtime_endpoint(simulator_url)
    base_payload: dict[str, Any] = {
        "success": True,
        "schema": GATEWAY_SUBMISSION_SCHEMA,
        "dry_run": dry_run,
        "target_endpoint": endpoint,
        "workflow_fingerprint": str(submission.get("workflow_fingerprint") or "")[:64],
        "mesh_payload_fingerprint": runtime_fingerprint,
        "route_action": route_action,
        "raw_payload_echoed": False,
        "datadog_tags": _datadog_tags(qlc_bundle, submission, "dry_run" if dry_run else "submit", "not_run", e2b_enabled),
    }
    if dry_run:
        base_payload["simulator_status"] = "not_run"
        base_payload["loop_receipt"] = build_gateway_loop_receipt(qlc_bundle, {"status": "not_run"})
        return base_payload

    try:
        response = _post_json(endpoint, runtime_payload, timeout=timeout)
    except (OSError, HTTPError, URLError, TimeoutError) as exc:
        failure = {
            **base_payload,
            "success": False,
            "simulator_status": "submit_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
        failure["datadog_tags"] = _datadog_tags(qlc_bundle, submission, "submit", "submit_failed", e2b_enabled)
        failure["loop_receipt"] = build_gateway_loop_receipt(qlc_bundle, {"status": "submit_failed"})
        return failure

    simulator_status = str(response.get("status") or "unknown")[:80]
    accepted = simulator_status == "ok"
    payload = {
        **base_payload,
        "success": accepted,
        "simulator_status": simulator_status,
        "response_fingerprint": _fingerprint(_compact_simulator_response(response)),
        "loop_receipt": build_gateway_loop_receipt(qlc_bundle, response),
    }
    payload["datadog_tags"] = _datadog_tags(qlc_bundle, submission, "submit", simulator_status, e2b_enabled)
    return payload


def extract_gateway_submission(qlc_bundle: Mapping[str, Any]) -> dict[str, Any]:
    _reject_forbidden_fields(qlc_bundle)
    if qlc_bundle.get("schema") == WORKFLOW_SCHEMA:
        submission = _mapping(qlc_bundle.get("gateway_submission"))
    elif qlc_bundle.get("schema") == GATEWAY_SUBMISSION_SCHEMA:
        submission = qlc_bundle
    else:
        raise ValueError("QLC submit requires a protection workflow bundle or gateway submission")
    if submission.get("schema") != GATEWAY_SUBMISSION_SCHEMA:
        raise ValueError("QLC gateway submission schema is missing")
    if not isinstance(submission.get("mesh_payload"), Mapping):
        raise ValueError("QLC gateway submission requires mesh_payload")
    _reject_forbidden_fields(submission)
    return dict(submission)


def build_gateway_loop_receipt(qlc_bundle: Mapping[str, Any], simulator_result: Mapping[str, Any]) -> dict[str, Any]:
    _reject_forbidden_fields(qlc_bundle)
    _reject_forbidden_fields(simulator_result)
    submission = extract_gateway_submission(qlc_bundle)
    route_action = str(submission.get("route_action") or "submit_to_cerebrum")
    simulator_status = str(simulator_result.get("status") or "unknown")[:80]
    if simulator_status not in {"ok", "accepted", "success", "not_run"}:
        route_action = "human_review"
    return {
        "schema": LOOP_RECEIPT_SCHEMA,
        "workflow_fingerprint": str(submission.get("workflow_fingerprint") or "")[:64],
        "simulator_status": simulator_status,
        "route_action": route_action,
        "prior_route_action": str(submission.get("route_action") or "")[:80],
        "fingerprints": {
            "gateway_submission": _fingerprint(submission),
            "mesh_payload": str(submission.get("mesh_payload_fingerprint") or _fingerprint(submission.get("mesh_payload") or {}))[:64],
            "simulator_result": _fingerprint(_compact_simulator_response(simulator_result)),
        },
        "raw_payload_embedded": False,
        "claim_boundary": "gateway_celebrum_loop_receipt_for_mvp_feedback_not_raw_runtime_evidence",
    }


def _runtime_endpoint(simulator_url: str) -> str:
    normalized = simulator_url.rstrip("/")
    if normalized.endswith(RUNTIME_PATH):
        return normalized
    return f"{normalized}{RUNTIME_PATH}"


def _post_json(url: str, payload: Mapping[str, Any], timeout: int) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    req = request.Request(
        url,
        data=encoded,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("simulator response must be a JSON object")
    return parsed


def _compact_simulator_response(response: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": str(response.get("status") or "unknown")[:80],
        "runtime_fingerprint": _fingerprint(response.get("runtime") or {}),
        "persistence_fingerprint": _fingerprint(response.get("persistence") or {}),
    }


def _datadog_tags(
    qlc_bundle: Mapping[str, Any],
    submission: Mapping[str, Any],
    gateway_mode: str,
    simulator_status: str,
    e2b_enabled: bool,
) -> list[str]:
    mesh_payload = _mapping(submission.get("mesh_payload"))
    plugin_context = _mapping(mesh_payload.get("plugin_context"))
    swop = _mapping(plugin_context.get("sensitivity_weighted_obfuscation_policy"))
    return [
        f"qlc_schema:{_tag_value(str(qlc_bundle.get('schema') or submission.get('schema') or 'unknown'))}",
        f"media_type:{_tag_value(str(qlc_bundle.get('media_type') or swop.get('media_type') or 'unknown'))}",
        f"swop_level:{_tag_value(str(swop.get('sensitivity_level') or 'unknown'))}",
        f"route_action:{_tag_value(str(submission.get('route_action') or 'unknown'))}",
        f"simulator_status:{_tag_value(simulator_status)}",
        f"gateway_mode:{_tag_value(gateway_mode)}",
        f"e2b_enabled:{str(bool(e2b_enabled)).lower()}",
    ]


def _reject_forbidden_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_QCL_SUBMISSION_FIELDS and normalized != "secret_manager_ref":
                raise ValueError(f"raw QLC submission field is not allowed: {key}")
            _reject_forbidden_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _reject_forbidden_fields(item)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tag_value(value: str) -> str:
    return value.lower().replace(" ", "_").replace(":", "_").replace(",", "_")[:120] or "unknown"
