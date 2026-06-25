from __future__ import annotations

import os
import re
import socket
from typing import Any, Mapping


GATEWAY_METRICS = {
    "submit_ok": "ffed_qlc.gateway.submit.ok",
    "submit_failed": "ffed_qlc.gateway.submit.failed",
    "review_required": "ffed_qlc.workflow.review_required",
    "e2b_audit_pass": "ffed_qlc.e2b.audit.pass",
    "e2b_audit_fail": "ffed_qlc.e2b.audit.fail",
}


def _sanitize(value: str, *, limit: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.\-/]", "_", str(value)).strip("_.-/")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned[:limit] or "unknown")


def emit_dogstatsd_counter(name: str, value: int = 1, tags: tuple[str, ...] = ()) -> bool:
    host = os.environ.get("DD_DOGSTATSD_HOST", "127.0.0.1")
    port = int(os.environ.get("DD_DOGSTATSD_PORT", "8125"))
    safe_name = _sanitize(name, limit=200)
    safe_tags = [_sanitize(t) for t in tags]
    tag_suffix = f"|#{','.join(safe_tags)}" if safe_tags else ""
    payload = f"{safe_name}:{value}|c{tag_suffix}".encode("utf-8")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(payload, (host, port))
        return True
    except OSError:
        return False


def emit_gateway_submit_counter(event: str, tags: list[str] | tuple[str, ...]) -> bool:
    metric = GATEWAY_METRICS.get(event, event)
    return emit_dogstatsd_counter(metric, tags=tuple(tags))
