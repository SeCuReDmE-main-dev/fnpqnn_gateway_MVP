"""Tunnel and IDE-forwarded URL helpers.

VS Code tunnels, Dev Tunnels, SSH forwards, and remote IDE port forwarding all
collapse to the same gateway contract: a user-approved HTTP(S) URL. The gateway
validates the URL shape and optionally probes it; it never reads IDE secrets.
"""

from __future__ import annotations

from .codeproject_client import normalize_url, status


def tunnel_status(url: str, dry_run: bool = False) -> dict[str, object]:
    normalized = normalize_url(url)
    probe = status(normalized, dry_run=dry_run)
    return {
        "success": bool(probe["success"]),
        "url": normalized,
        "dry_run": dry_run,
        "transport": "user-approved-http-url",
        "stores_credentials": False,
        "credential_storage": "none",
        "probe": probe,
        "next_step": None if probe["success"] else "Verify the VS Code/IDE tunnel forwards CodeProject.AI Server port 32168.",
    }
