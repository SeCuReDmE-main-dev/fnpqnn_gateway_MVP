"""QLC workflow bundle submission to the FNP-QNN simulator boundary."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .qlc_env import DEFAULT_OPENCLAW_ENV, load_openclaw_tool_env
from .telemetry import emit_gateway_submit_counter


WORKFLOW_SCHEMA = "ffed.qlc.protection_workflow_bundle.v1"
GATEWAY_SUBMISSION_SCHEMA = "ffed.qlc.gateway_submission.v1"
LOOP_RECEIPT_SCHEMA = "ffed.qlc.gateway_celebrum_loop_receipt.v1"
QLC_WIRING_CONTRACT_VERSION = "qlc-wiring-contract.v2"
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
    env_file: str | Path | None = DEFAULT_OPENCLAW_ENV,
    emit_metrics: bool = False,
) -> dict[str, Any]:
    """Validate a QLC bundle and optionally submit its mesh payload to Cerebrum."""

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    _validate_simulator_url(simulator_url)
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
        "submission_fingerprint": _fingerprint(submission),
        "route_action": route_action,
        "raw_payload_echoed": False,
        "env_preflight": load_openclaw_tool_env(env_file) if e2b_enabled or emit_metrics else _env_not_loaded(env_file),
        "datadog_tags": _datadog_tags(qlc_bundle, submission, "dry_run" if dry_run else "submit", "not_run", e2b_enabled),
    }
    if dry_run:
        base_payload["simulator_status"] = "not_run"
        base_payload["gateway_status"] = "dry_run"
        base_payload["loop_receipt"] = build_gateway_loop_receipt(qlc_bundle, {"status": "not_run"})
        _maybe_emit_submit_metric("submit_ok", base_payload, emit_metrics)
        return base_payload

    try:
        response = _post_json(endpoint, runtime_payload, timeout=timeout)
    except (OSError, HTTPError, URLError, TimeoutError) as exc:
        failure = {
            **base_payload,
            "success": False,
            "simulator_status": "submit_failed",
            "gateway_status": "submit_failed",
            "error_type": type(exc).__name__,
            "error": _compact_error(exc),
        }
        failure["datadog_tags"] = _datadog_tags(qlc_bundle, submission, "submit", "submit_failed", e2b_enabled)
        failure["loop_receipt"] = build_gateway_loop_receipt(qlc_bundle, {"status": "submit_failed"})
        _maybe_emit_submit_metric("submit_failed", failure, emit_metrics)
        return failure

    simulator_status = str(response.get("status") or "unknown")[:80]
    accepted = simulator_status == "ok"
    payload = {
        **base_payload,
        "success": accepted,
        "simulator_status": simulator_status,
        "gateway_status": "accepted" if accepted else "simulator_rejected",
        "response_fingerprint": _fingerprint(_compact_simulator_response(response)),
        "loop_receipt": build_gateway_loop_receipt(qlc_bundle, response),
    }
    payload["datadog_tags"] = _datadog_tags(qlc_bundle, submission, "submit", simulator_status, e2b_enabled)
    _maybe_emit_submit_metric("submit_ok" if accepted else "submit_failed", payload, emit_metrics)
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
    _validate_contract_version(qlc_bundle, submission)
    if not isinstance(submission.get("mesh_payload"), Mapping):
        raise ValueError("QLC gateway submission requires mesh_payload")
    _reject_forbidden_fields(submission)
    return dict(submission)


def _validate_contract_version(qlc_bundle: Mapping[str, Any], submission: Mapping[str, Any]) -> None:
    bundle_version = str(qlc_bundle.get("contract_version") or "")[:80]
    submission_version = str(submission.get("contract_version") or "")[:80]
    contract_version = bundle_version or submission_version
    if contract_version != QLC_WIRING_CONTRACT_VERSION:
        raise ValueError("QLC contract_version is missing or unsupported")
    if submission_version and submission_version != contract_version:
        raise ValueError("QLC gateway submission contract_version mismatch")


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
    _validate_simulator_url(simulator_url)
    normalized = simulator_url.rstrip("/")
    if normalized.endswith(RUNTIME_PATH):
        return normalized
    return f"{normalized}{RUNTIME_PATH}"


def _validate_simulator_url(simulator_url: str) -> None:
    parsed = urlparse(simulator_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("simulator_url must use HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("simulator_url must not include userinfo")
    if not parsed.hostname:
        raise ValueError("simulator_url must include a host")
    host = parsed.hostname.strip().lower()
    if host == "localhost":
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("simulator_url must target localhost or a loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("simulator_url must target localhost or a loopback IP")


def _env_not_loaded(env_file: str | Path | None) -> dict[str, Any]:
    path = Path(env_file).expanduser() if env_file else DEFAULT_OPENCLAW_ENV
    return {
        "success": True,
        "path": str(path),
        "loaded": [],
        "presence": {},
        "raw_values_printed": False,
        "status": "not_loaded",
    }


def _compact_error(exc: BaseException) -> str:
    text = str(exc).replace("\n", " ").strip()
    return f"{type(exc).__name__}: {text[:160]}"


def _maybe_emit_submit_metric(event: str, payload: Mapping[str, Any], emit_metrics: bool) -> None:
    if emit_metrics:
        emit_gateway_submit_counter(event, tuple(str(tag) for tag in payload.get("datadog_tags", ())))


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
