"""Diagnostics for CodeProject.AI Server mesh mode.

The gateway does not edit CodeProject.AI `appsettings.json` in v1. It reports
the exact mesh settings and Docker port mappings an operator should review.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from .codeproject_client import normalize_url, status


DOCKER_TCP_MAPPING = "-p 32168:32168"
DOCKER_UDP_MAPPING = "-p 32168:32168/udp"
MESH_SETTINGS = (
    "MeshOptions.Enable",
    "MeshOptions.EnableBroadcasting",
    "MeshOptions.MonitorNetwork",
    "MeshOptions.AcceptForwardedRequests",
    "MeshOptions.AllowRequestForwarding",
    "MeshOptions.KnownMeshHostnames",
)


def _host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(normalize_url(url))
    return parsed.hostname or "localhost", parsed.port or (443 if parsed.scheme == "https" else 80)


def tcp_probe(url: str, timeout: float = 2.0) -> dict[str, object]:
    host, port = _host_port(url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"success": True, "host": host, "port": port, "detail": "TCP connection accepted"}
    except OSError as exc:
        return {"success": False, "host": host, "port": port, "detail": f"{type(exc).__name__}: {exc}"}


def mesh_status(
    url: str = "http://localhost:32168",
    known_servers: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    normalized = normalize_url(url)
    tcp = {"success": True, "detail": "dry-run; TCP not probed"} if dry_run else tcp_probe(normalized)
    http = status(normalized, dry_run=dry_run)
    known = known_servers or []
    return {
        "success": bool(tcp["success"] and http["success"]),
        "url": normalized,
        "dry_run": dry_run,
        "tcp": tcp,
        "http": http,
        "mesh_settings_to_review": list(MESH_SETTINGS),
        "known_servers": known,
        "known_servers_instruction": {
            "appsettings_branch": "MeshOptions.KnownMeshHostnames",
            "value": known,
            "note": "Use this when UDP broadcast cannot discover Docker or remote servers.",
        },
        "docker_port_mappings": [DOCKER_TCP_MAPPING, DOCKER_UDP_MAPPING],
        "docker_publish": [DOCKER_TCP_MAPPING, DOCKER_UDP_MAPPING],
        "warning": "Expose UDP 32168 for mesh broadcast when running CodeProject.AI Server in Docker.",
        "mutated_config": False,
        "mutates_config": False,
    }
