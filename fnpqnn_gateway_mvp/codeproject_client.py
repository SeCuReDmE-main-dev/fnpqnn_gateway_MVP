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
