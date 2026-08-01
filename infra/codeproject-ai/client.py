"""Secret-free CodeProject.AI mesh connector.

This module is intentionally standard-library only. It returns bounded,
versioned envelopes and never logs images, detections, credentials, or raw
server responses.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SCHEMA = "securedme.codeproject.mesh.v1"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ERROR_CODES = {
    "NODE_UNAVAILABLE",
    "MODULE_UNAVAILABLE",
    "TIMEOUT",
    "INVALID_INPUT",
    "MESH_DEGRADED",
}


class ConnectorError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError("unknown connector error code")
        self.code = code
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _node() -> dict[str, object]:
    return json.loads((Path(__file__).with_name("node.json")).read_text(encoding="utf-8"))


def _base_url(explicit: str | None = None) -> str:
    if explicit:
        value = explicit.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ConnectorError("INVALID_INPUT", "base URL must use http or https")
        return value
    return f"http://127.0.0.1:{_node()['host_port']}"


def _request(path: str, *, base_url: str | None = None, timeout: float = 8.0,
             method: str = "GET", body: bytes | None = None,
             content_type: str | None = None, force_local: bool = False) -> dict[str, object]:
    if timeout <= 0 or timeout > 120:
        raise ConnectorError("INVALID_INPUT", "timeout must be between 0 and 120 seconds")
    headers = {"Accept": "application/json", "User-Agent": "securedme-cpai-mesh/1"}
    if content_type:
        headers["Content-Type"] = content_type
    if force_local:
        headers["X-CPAI-Forwarded"] = "true"
    request = Request(urljoin(_base_url(base_url) + "/", path.lstrip("/")),
                      data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(4 * 1024 * 1024)
    except HTTPError as exc:
        code = "MODULE_UNAVAILABLE" if exc.code in (404, 503) else "NODE_UNAVAILABLE"
        raise ConnectorError(code, f"CodeProject.AI returned HTTP {exc.code}") from exc
    except TimeoutError as exc:
        raise ConnectorError("TIMEOUT", "CodeProject.AI request timed out") from exc
    except (URLError, OSError) as exc:
        raise ConnectorError("NODE_UNAVAILABLE", "CodeProject.AI node is unavailable") from exc
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorError("NODE_UNAVAILABLE", "CodeProject.AI returned an invalid JSON response") from exc
    if not isinstance(decoded, dict):
        raise ConnectorError("NODE_UNAVAILABLE", "CodeProject.AI returned an invalid response envelope")
    return decoded


def _envelope(status: str, data: dict[str, object] | None = None,
              error: ConnectorError | None = None) -> dict[str, object]:
    node = _node()
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": status,
        "request_id": uuid.uuid4().hex,
        "timestamp_utc": _now(),
        "node_id": node["node_id"],
        "app_id": node["app_id"],
    }
    if data is not None:
        result["data"] = data
    if error is not None:
        result["error"] = {"code": error.code, "message": str(error)}
    return result


def health(*, base_url: str | None = None, timeout: float = 8.0) -> dict[str, object]:
    try:
        payload = _request("/v1/server/status/ping", base_url=base_url, timeout=timeout)
        return _envelope("success", {
            "ready": payload.get("success") is True,
            "version": payload.get("message"),
            "hostname": payload.get("hostname"),
        })
    except ConnectorError as exc:
        return _envelope("error", error=exc)


def capabilities(*, base_url: str | None = None, timeout: float = 15.0) -> dict[str, object]:
    try:
        payload = _request("/v1/module/list/status", base_url=base_url, timeout=timeout)
        modules = []
        for item in payload.get("statuses", []):
            if not isinstance(item, dict):
                continue
            modules.append({
                "module_id": item.get("moduleId"),
                "name": item.get("name"),
                "version": item.get("version"),
                "status": item.get("status"),
            })
        return _envelope("success", {"modules": modules})
    except ConnectorError as exc:
        return _envelope("error", error=exc)


def mesh_status(*, base_url: str | None = None, timeout: float = 8.0) -> dict[str, object]:
    try:
        payload = _request("/v1/server/mesh/summary", base_url=base_url, timeout=timeout)
        local = payload.get("localServer") if isinstance(payload.get("localServer"), dict) else {}
        status = local.get("status") if isinstance(local.get("status"), dict) else {}
        peers = [item for item in payload.get("serverInfos", []) if isinstance(item, dict) and not item.get("isLocalServer")]
        data = {
            "active": local.get("isActive") is True,
            "broadcasting": status.get("isBroadcasting") is True,
            "monitoring": status.get("isMonitoring") is True,
            "accept_forwarded": status.get("acceptForwardedRequests") is True,
            "allow_forwarding": status.get("allowRequestForwarding") is True,
            "known_hosts": len(status.get("knownHostnames") or []),
            "active_peers": sum(1 for peer in peers if peer.get("isActive") is True),
            "peer_hostnames": sorted(str(peer.get("callableHostname")) for peer in peers if peer.get("callableHostname")),
        }
        data["mesh_degraded"] = not data["active"] or data["active_peers"] < data["known_hosts"]
        return _envelope("degraded" if data["mesh_degraded"] else "success", data)
    except ConnectorError as exc:
        return _envelope("error", error=exc)


def detect(image: str | Path, *, base_url: str | None = None,
           timeout: float = 60.0, min_confidence: float = 0.4, local_only: bool = False) -> dict[str, object]:
    path = Path(image)
    if not path.is_file():
        return _envelope("error", error=ConnectorError("INVALID_INPUT", "image file does not exist"))
    size = path.stat().st_size
    if size <= 0 or size > MAX_IMAGE_BYTES:
        return _envelope("error", error=ConnectorError("INVALID_INPUT", "image size is outside the 1 byte to 20 MiB limit"))
    if not 0.0 <= min_confidence <= 1.0:
        return _envelope("error", error=ConnectorError("INVALID_INPUT", "min_confidence must be between 0 and 1"))

    boundary = f"----securedme-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"min_confidence\"\r\n\r\n{min_confidence}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"fixture{path.suffix}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    try:
        payload = _request("/v1/vision/detection", base_url=base_url, timeout=timeout,
                           method="POST", body=b"".join(parts),
                           content_type=f"multipart/form-data; boundary={boundary}", force_local=local_only)
        if payload.get("success") is not True:
            raise ConnectorError("MODULE_UNAVAILABLE", "YOLO detection module did not complete the request")
        predictions = []
        for item in payload.get("predictions", []):
            if not isinstance(item, dict):
                continue
            predictions.append({
                "label": item.get("label"),
                "confidence": item.get("confidence"),
                "x_min": item.get("x_min"),
                "y_min": item.get("y_min"),
                "x_max": item.get("x_max"),
                "y_max": item.get("y_max"),
            })
        return _envelope("success", {
            "success": payload.get("success") is True,
            "processed_by": payload.get("processedBy"),
            "inference_ms": payload.get("inferenceMs"),
            "analysis_round_trip_ms": payload.get("analysisRoundTripMs"),
            "predictions": predictions,
        })
    except ConnectorError as exc:
        return _envelope("error", error=exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SecuredMe CodeProject.AI mesh connector")
    parser.add_argument("operation", choices=("health", "capabilities", "mesh", "detect"))
    parser.add_argument("--url")
    parser.add_argument("--image")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--min-confidence", type=float, default=0.4)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args(argv)
    if args.operation == "health":
        result = health(base_url=args.url, timeout=args.timeout)
    elif args.operation == "capabilities":
        result = capabilities(base_url=args.url, timeout=args.timeout)
    elif args.operation == "mesh":
        result = mesh_status(base_url=args.url, timeout=args.timeout)
    else:
        if not args.image:
            result = _envelope("error", error=ConnectorError("INVALID_INPUT", "--image is required for detect"))
        else:
            result = detect(args.image, base_url=args.url, timeout=args.timeout, min_confidence=args.min_confidence, local_only=args.local_only)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0 if result["status"] in ("success", "degraded") else 1


if __name__ == "__main__":
    sys.exit(main())
