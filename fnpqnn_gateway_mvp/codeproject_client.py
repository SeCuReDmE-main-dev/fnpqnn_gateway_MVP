"""Small HTTP client for CodeProject.AI Server.

The client uses the standard library only. It never stores credentials because a
CodeProject.AI Server connection is a local/mesh/tunnel URL, not a cloud account
login in this gateway.
"""

from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 4.0
KNOWN_PROBE_ROUTES = (
    "/",
    "/v1/vision/detect/scene",
)
DEFAULT_PROBE_ROUTES = KNOWN_PROBE_ROUTES
YOLO_PROBE_ROUTES = (
    "/v1/vision/detection",
    "/v1/vision/custom/list",
    "/v1/vision/custom/<model-name>",
)
YOLO_TRAINING_MODULE = {
    "module_id": "TrainingObjectDetectionYOLOv5",
    "name": "Training for YoloV5 6.2",
    "version": "1.7.0",
    "category": "Training",
    "stack": "Python, PyTorch, YOLO",
    "based_on": "Ultralytics YOLOv5",
    "repo": "https://github.com/codeproject/CodeProject.AI-TrainingObjectDetectionYOLOv5",
}
YOLO_TRAINING_ROUTES = {
    "create_dataset": "/v1/train/create_dataset",
    "train_model": "/v1/train/train_model",
    "resume_training": "/v1/train/resume_training",
    "model_info": "/v1/train/model_info",
    "dataset_info": "/v1/train/dataset_info",
}


def normalize_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("CodeProject.AI URL must not be empty")
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "http://" + cleaned
    return cleaned.rstrip("/")


def _encode_multipart(files: dict[str, str | Path], fields: dict[str, object] | None = None) -> tuple[bytes, str]:
    boundary = f"----fnpqnn-gateway-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in (fields or {}).items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    for field_name, file_path in files.items():
        path = Path(file_path)
        filename = path.name
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode())
        chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request(
    route: str,
    url: str = "http://localhost:32168",
    method: str = "GET",
    timeout: float = DEFAULT_TIMEOUT,
    payload: dict[str, object] | bytes | None = None,
    files: dict[str, str | Path] | None = None,
) -> dict[str, object]:
    """Perform a generic CodeProject.AI HTTP request.

    This wrapper is intentionally conservative: v1 only sends simple requests
    and reports response metadata. Module-specific payload helpers can be added
    later without changing the gateway hook contract.
    """

    base = normalize_url(url) + "/"
    target = urljoin(base, route.lstrip("/"))
    headers = {"User-Agent": "fnpqnn-gateway-mvp/0.1"}
    data: bytes | None = None
    if files:
        fields = payload if isinstance(payload, dict) else None
        data, content_type = _encode_multipart(files, fields)
        headers["Content-Type"] = content_type
        method = "POST" if method == "GET" else method
    elif payload is not None:
        if isinstance(payload, bytes):
            data = payload
            headers["Content-Type"] = "application/octet-stream"
        else:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        method = "POST" if method == "GET" else method
    req = Request(target, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read(4096)
            text = body.decode("utf-8", errors="replace")
            parsed: object | None = None
            if text.strip().startswith(("{", "[")):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
            return {
                "success": True,
                "url": target,
                "status": response.status,
                "content_type": response.headers.get("content-type"),
                "body_preview": text[:1000],
                "json": parsed,
            }
    except HTTPError as exc:
        return {
            "success": False,
            "url": target,
            "status": exc.code,
            "error": f"HTTPError: {exc.reason}",
            "body_preview": exc.read(1000).decode("utf-8", errors="replace"),
        }
    except (URLError, OSError, TimeoutError) as exc:
        return {"success": False, "url": target, "status": None, "error": f"{type(exc).__name__}: {exc}"}


def status(url: str = "http://localhost:32168", timeout: float = DEFAULT_TIMEOUT, dry_run: bool = False) -> dict[str, object]:
    normalized = normalize_url(url)
    if dry_run:
        routes = list(KNOWN_PROBE_ROUTES)
        return {
            "success": True,
            "dry_run": True,
            "url": normalized,
            "routes": routes,
            "checks": [normalized + route for route in routes],
            "note": "No network request was made.",
        }
    root = request("/", normalized, timeout=timeout)
    return {
        "success": bool(root["success"]),
        "url": normalized,
        "reachable": bool(root["success"]),
        "root": root,
        "next_step": None if root["success"] else "Start CodeProject.AI Server or provide a forwarded tunnel URL.",
    }


def module_probe(url: str = "http://localhost:32168", timeout: float = DEFAULT_TIMEOUT, dry_run: bool = False) -> dict[str, object]:
    normalized = normalize_url(url)
    if dry_run:
        return {"success": True, "dry_run": True, "url": normalized, "routes": list(KNOWN_PROBE_ROUTES)}
    results = [request(route, normalized, timeout=timeout) for route in KNOWN_PROBE_ROUTES]
    return {
        "success": any(bool(item["success"]) for item in results),
        "url": normalized,
        "routes": results,
        "warning": "Module routes may return 404/405 when modules are not installed; this is not a gateway failure.",
    }


def yolo_probe(
    url: str = "http://localhost:32168",
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
    image_path: str | Path | None = None,
    min_confidence: float = 0.4,
) -> dict[str, object]:
    """Probe CodeProject.AI as a YOLO/instruct-capable backend.

    CodeProject.AI modules vary by installation. This probe is intentionally
    non-authoritative: it checks common/declared routes and reports whether the
    server transport is available without assuming a specific module is installed.
    """

    normalized = normalize_url(url)
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "url": normalized,
            "routes": list(YOLO_PROBE_ROUTES),
            "method": "POST",
            "file_field": "image",
            "min_confidence": min_confidence,
            "backend_role": "codeproject-ai-yolo-instruct",
            "training_module": YOLO_TRAINING_MODULE,
            "next_step": "Use --image to perform an actual YOLO detection request, or run without --image to check server/list-model transport only.",
        }
    root = status(normalized, timeout=timeout)
    results: list[dict[str, object]] = []
    custom_list = request("/v1/vision/custom/list", normalized, method="POST", timeout=timeout)
    results.append(custom_list)
    detection: dict[str, object] | None = None
    if image_path is not None:
        detection = request(
            "/v1/vision/detection",
            normalized,
            method="POST",
            timeout=timeout,
            payload={"min_confidence": min_confidence},
            files={"image": image_path},
        )
        results.append(detection)
    available = [item for item in results if item.get("success")]
    return {
        "success": bool(root["success"]),
        "url": normalized,
        "server_reachable": bool(root["success"]),
        "backend_role": "codeproject-ai-yolo-instruct",
        "training_module": YOLO_TRAINING_MODULE,
        "official_routes": {
            "standard_detection": "/v1/vision/detection",
            "custom_model": "/v1/vision/custom/<model-name>",
            "custom_model_list": "/v1/vision/custom/list",
        },
        "method": "POST",
        "file_field": "image",
        "min_confidence": min_confidence,
        "image_supplied": image_path is not None,
        "routes": results,
        "available_route_count": len(available),
        "yolo_route_available": bool(detection and detection.get("success")),
        "warning": "Without --image, yolo_route_available remains false because no object-detection inference was requested.",
        "cerebrum_relation": {
            "simulator_surface": "Cerebrum runtime endpoints are consumed through FNP-QNN CLI/HTTP, not imported into CodeProject.AI.",
            "handoff": "YOLO detections/instruct outputs should be transformed into simulator gate or memory events by the native agent/tool.",
        },
    }


def yolo_training_probe(
    url: str = "http://localhost:32168",
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
    model_name: str | None = None,
    dataset_name: str | None = None,
) -> dict[str, object]:
    """Probe the explicit CodeProject.AI YOLOv5 6.2 training module.

    This function only calls non-destructive info endpoints unless the user later
    adds a separate explicit training command. Dataset creation and model
    training are returned as documented routes, not executed here.
    """

    normalized = normalize_url(url)
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "url": normalized,
            "module": YOLO_TRAINING_MODULE,
            "routes": YOLO_TRAINING_ROUTES,
            "safe_probe_routes": ["model_info", "dataset_info"],
            "destructive_or_long_running_routes": ["create_dataset", "train_model", "resume_training"],
            "next_step": "Provide --model-name or --dataset-name without --dry-run to query info routes only.",
        }
    root = status(normalized, timeout=timeout)
    results: list[dict[str, object]] = []
    if model_name:
        results.append(request(YOLO_TRAINING_ROUTES["model_info"], normalized, method="POST", timeout=timeout, payload={"model_name": model_name}))
    if dataset_name:
        results.append(request(YOLO_TRAINING_ROUTES["dataset_info"], normalized, method="POST", timeout=timeout, payload={"dataset_name": dataset_name}))
    return {
        "success": bool(root["success"]),
        "url": normalized,
        "server_reachable": bool(root["success"]),
        "module": YOLO_TRAINING_MODULE,
        "routes": YOLO_TRAINING_ROUTES,
        "safe_probe_results": results,
        "long_running_actions_not_executed": ["create_dataset", "train_model", "resume_training"],
        "cerebrum_relation": {
            "verified_local_surface": "FNP-QNN exposes Cerebrum runtime endpoints locally; trained YOLO model results should be bridged through CLI/HTTP artifacts.",
            "handoff": "Native agent uses CodeProject.AI trainer and simulator gate docs; gateway records the path without absorbing either system.",
        },
    }
