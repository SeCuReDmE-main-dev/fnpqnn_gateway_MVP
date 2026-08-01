"""Versioned, redacted contract for the SecuredMe CodeProject.AI mesh."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .codeproject_client import normalize_url, request

CONTRACT_VERSION = "securedme.codeproject.mesh.v1"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:32173"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ERROR_CODES = {
    "NODE_UNAVAILABLE",
    "MODULE_UNAVAILABLE",
    "TIMEOUT",
    "INVALID_INPUT",
    "MESH_DEGRADED",
}

RequestFn = Callable[..., dict[str, object]]


def _envelope(status: str, operation: str, *, node_id: str = "cpai-gateway", **payload: Any) -> dict[str, Any]:
    return {
        "contract": CONTRACT_VERSION,
        "status": status,
        "operation": operation,
        "node_id": node_id,
        **payload,
        "secret_values_exposed": False,
    }


def _error(operation: str, code: str, message: str) -> dict[str, Any]:
    if code not in ERROR_CODES:
        code = "NODE_UNAVAILABLE"
    return _envelope("error", operation, error_code=code, message=message)


def _mesh_payload(url: str, timeout: float, requester: RequestFn) -> tuple[dict[str, object] | None, dict[str, Any] | None]:
    response = requester("/v1/server/mesh/status", normalize_url(url), timeout=timeout)
    if not response.get("success"):
        return None, _error("mesh_status", "NODE_UNAVAILABLE", "CodeProject.AI mesh node is unavailable.")
    payload = response.get("json")
    if not isinstance(payload, dict):
        return None, _error("mesh_status", "NODE_UNAVAILABLE", "CodeProject.AI returned an invalid mesh response.")
    return payload, None


def gateway_health(
    url: str = DEFAULT_GATEWAY_URL,
    timeout: float = 5.0,
    *,
    requester: RequestFn = request,
) -> dict[str, Any]:
    payload, error = _mesh_payload(url, timeout, requester)
    if error:
        error["operation"] = "health"
        return error
    assert payload is not None
    return _envelope(
        "success",
        "health",
        node_id=str(payload.get("hostname") or "cpai-gateway"),
        reachable=True,
        platform=str(payload.get("platform") or "unknown"),
        system_description=str(payload.get("systemDescription") or "unknown"),
        mesh_enabled=bool(payload.get("success")),
    )


def gateway_capabilities(
    url: str = DEFAULT_GATEWAY_URL,
    timeout: float = 5.0,
    *,
    requester: RequestFn = request,
) -> dict[str, Any]:
    payload, error = _mesh_payload(url, timeout, requester)
    if error:
        error["operation"] = "capabilities"
        return error
    assert payload is not None
    routes = payload.get("enabledRoutes")
    safe_routes = sorted(str(route) for route in routes) if isinstance(routes, list) else []
    return _envelope(
        "success",
        "capabilities",
        node_id=str(payload.get("hostname") or "cpai-gateway"),
        routes=safe_routes,
        yolo_detection_available="vision/detection" in safe_routes,
    )


def gateway_mesh_status(
    url: str = DEFAULT_GATEWAY_URL,
    timeout: float = 5.0,
    expected_peer_count: int = 11,
    *,
    requester: RequestFn = request,
) -> dict[str, Any]:
    response = requester("/v1/server/mesh/summary", normalize_url(url), timeout=timeout)
    if not response.get("success") or not isinstance(response.get("json"), dict):
        return _error("mesh_status", "NODE_UNAVAILABLE", "CodeProject.AI mesh summary is unavailable.")
    summary = response["json"]
    local = summary.get("localServer") if isinstance(summary.get("localServer"), dict) else {}
    payload = local.get("status") if isinstance(local.get("status"), dict) else {}
    hosts = payload.get("knownHostnames")
    known_hosts = sorted(str(host) for host in hosts) if isinstance(hosts, list) else []
    server_infos = summary.get("serverInfos") if isinstance(summary.get("serverInfos"), list) else []
    active_peers = sorted(
        str(item.get("status", {}).get("hostname") or item.get("callableHostname"))
        for item in server_infos
        if isinstance(item, dict) and not item.get("isLocalServer") and item.get("isActive") is True
    )
    policy = {
        "broadcasting": bool(payload.get("isBroadcasting")),
        "monitoring": bool(payload.get("isMonitoring")),
        "accept_forwarded": bool(payload.get("acceptForwardedRequests")),
        "allow_forwarding": bool(payload.get("allowRequestForwarding")),
    }
    ready = local.get("isActive") is True and len(known_hosts) >= expected_peer_count and len(active_peers) >= expected_peer_count and all(policy.values())
    return _envelope(
        "success" if ready else "degraded",
        "mesh_status",
        node_id=str(payload.get("hostname") or "cpai-gateway"),
        known_hosts=known_hosts,
        known_peer_count=len(known_hosts),
        active_peer_count=len(active_peers),
        active_peers=active_peers,
        expected_peer_count=expected_peer_count,
        policy=policy,
        error_code=None if ready else "MESH_DEGRADED",
    )


def gateway_detect(
    image_path: str,
    url: str = DEFAULT_GATEWAY_URL,
    timeout: float = 60.0,
    min_confidence: float = 0.4,
    *,
    requester: RequestFn = request,
) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        return _error("detect", "INVALID_INPUT", "Image file does not exist.")
    size = path.stat().st_size
    if size <= 0 or size > MAX_IMAGE_BYTES:
        return _error("detect", "INVALID_INPUT", "Image size is outside the accepted range.")
    if not 0.0 <= min_confidence <= 1.0:
        return _error("detect", "INVALID_INPUT", "min_confidence must be between 0 and 1.")
    response = requester(
        "/v1/vision/detection",
        normalize_url(url),
        method="POST",
        timeout=timeout,
        payload={"min_confidence": min_confidence},
        files={"image": path},
        extra_headers={"X-CPAI-Forwarded": "true"},
    )
    if not response.get("success"):
        status_code = response.get("status")
        code = "MODULE_UNAVAILABLE" if status_code in {404, 405, 500, 503} else "NODE_UNAVAILABLE"
        return _error("detect", code, "YOLO detection is unavailable on the selected node.")
    payload = response.get("json")
    if not isinstance(payload, dict):
        return _error("detect", "MODULE_UNAVAILABLE", "YOLO returned an invalid response.")
    raw_predictions = payload.get("predictions")
    predictions: list[dict[str, Any]] = []
    if isinstance(raw_predictions, list):
        for prediction in raw_predictions[:500]:
            if not isinstance(prediction, dict):
                continue
            predictions.append(
                {
                    "label": str(prediction.get("label") or "unknown")[:128],
                    "confidence": prediction.get("confidence"),
                    "x_min": prediction.get("x_min"),
                    "y_min": prediction.get("y_min"),
                    "x_max": prediction.get("x_max"),
                    "y_max": prediction.get("y_max"),
                }
            )
    return _envelope(
        "success",
        "detect",
        node_id=str(payload.get("hostname") or "cpai-gateway"),
        inference_success=bool(payload.get("success", True)),
        prediction_count=len(predictions),
        predictions=predictions,
        image_sha_or_content_returned=False,
    )
