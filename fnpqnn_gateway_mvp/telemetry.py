"""Optional local OTLP counters. Transport failure never grants or denies access."""
from __future__ import annotations

import os
import re
import json
import time
from urllib import request
from urllib.parse import urlsplit


GATEWAY_METRICS = {
    "submit_ok": "ffed_qlc.gateway.submit.ok",
    "submit_failed": "ffed_qlc.gateway.submit.failed",
    "review_required": "ffed_qlc.workflow.review_required",
    "e2b_audit_pass": "ffed_qlc.e2b.audit.pass",
    "e2b_audit_fail": "ffed_qlc.e2b.audit.fail",
    "enforcer_check": "securedme.education.auth.enforcer_check",
    "secret_reject": "securedme.education.auth.secret_reject",
    "adapter_drift": "securedme.education.auth.adapter_drift",
    "template_missing": "securedme.education.auth.template_missing",
    "telemetry_drop": "securedme.education.auth.telemetry_drop",
}


def _sanitize(value: str, *, limit: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.\-/]", "_", str(value)).strip("_.-/")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned[:limit] or "unknown")


ATTRIBUTE_VALUES = {
    "platform": {"codex", "antigravity"},
    "decision": {"allow", "block"},
    "env": {"local", "staging", "production", "education-mvp"},
    "gateway_mode": {"dry_run", "submit"},
    "simulator_status": {"not_run", "submit_failed", "success", "ok", "unknown"},
    "e2b_enabled": {"true", "false"},
    "route": {"suite-auth-audit", "suite-auth-check", "qlc-submit"},
}


def local_metrics_endpoint(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}
            and parsed.port == 4318 and parsed.path == "/v1/metrics"
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        return False


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def emit_otel_counter(name: str, value: int = 1, tags: tuple[str, ...] = ()) -> bool:
    if os.environ.get("SECUREDME_OTEL_ENABLED", "").lower() != "true":
        return False
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://127.0.0.1:4318/v1/metrics")
    if not local_metrics_endpoint(endpoint) or name not in GATEWAY_METRICS.values():
        return False
    if type(value) is not int or not 1 <= value <= 1000:
        return False
    attributes = {}
    for tag in tags[:20]:
        if not isinstance(tag, str) or len(tag) > 160:
            continue
        key, separator, item = tag.partition(":")
        if separator and item in ATTRIBUTE_VALUES.get(key, set()):
            attributes[key] = item
    timestamp = str(time.time_ns())
    payload = {"resourceMetrics": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "securedme-education-gateway"}}]},
        "scopeMetrics": [{"scope": {"name": "securedme.education.gateway", "version": "1"}, "metrics": [{
            "name": name, "unit": "1", "sum": {
                "aggregationTemporality": 1, "isMonotonic": True,
                "dataPoints": [{"asInt": str(value), "startTimeUnixNano": timestamp, "timeUnixNano": timestamp,
                    "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in sorted(attributes.items())]}],
            },
        }]}],
    }]}
    try:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())
        req = request.Request(endpoint, body, {"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with opener.open(req, timeout=0.5) as response:
            raw = response.read(8193)
            if len(raw) > 8192 or response.status != 200:
                return False
        result = json.loads(raw or b"{}")
        partial = result.get("partialSuccess", {})
        return isinstance(partial, dict) and int(partial.get("rejectedDataPoints", 0)) == 0
    except (OSError, TypeError, ValueError, AttributeError):
        return False


def emit_gateway_submit_counter(event: str, tags: list[str] | tuple[str, ...]) -> bool:
    metric = GATEWAY_METRICS.get(event)
    return emit_otel_counter(metric, tags=tuple(tags)) if metric else False
