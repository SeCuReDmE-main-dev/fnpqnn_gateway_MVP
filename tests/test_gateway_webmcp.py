import sqlite3
import io
import json
from pathlib import Path

import pytest

from fnpqnn_gateway_mvp.gateway_webmcp import COMMON_TOOLS, GatewayWebMCPStore, THEME, manifest


def test_manifest_has_exact_tools_and_forbidden_boundaries():
    payload = manifest()
    names = [item["name"] for item in payload["tools"]]
    assert payload["schema"] == "securedme.webmcp.v1"
    assert len(payload["tools"]) == 12
    assert len([name for name in names if name.startswith("gateway_")]) == 10
    assert set(COMMON_TOOLS).issubset(names)
    assert "E2B" in payload["boundaries"]["externalWrites"]
    assert "browser automation" in payload["boundaries"]["externalWrites"]
    assert payload["product"]["slug"] == "gateway"
    assert all(entry["inputSchema"]["additionalProperties"] is False for entry in payload["tools"])
    assert all(entry["outputSchema"]["type"] == "object" for entry in payload["tools"])
    assert all(entry["handler"]["kind"] for entry in payload["tools"])


def test_static_exports_match_runtime_and_evidence_gate_shape():
    root = Path(__file__).parents[1]
    assert json.loads((root / "webmcp" / "manifest.json").read_text(encoding="utf-8")) == manifest()
    fixtures = json.loads((root / "webmcp" / "fixtures.json").read_text(encoding="utf-8"))
    assert set(fixtures) == {"tools", "journeys"}
    assert set(fixtures["tools"]) == {item["name"] for item in manifest()["tools"]}
    assert len(fixtures["journeys"]) == 6


def test_pointer_is_sanitized_audience_bound_and_one_time():
    store = GatewayWebMCPStore(sqlite3.connect(":memory:"))
    created = store.create_pointer({"hero": "Qbit", "provider_token": "never"}, audience="quanthor", ttl_seconds=300)
    with pytest.raises(ValueError):
        store.resolve_pointer(created["pointer"], audience="fnp-qnn")
    resolved = store.resolve_pointer(created["pointer"], audience="quanthor")
    assert resolved["content"] == {"hero": "Qbit"}
    assert resolved["one_time"] is True
    with pytest.raises(ValueError):
        store.resolve_pointer(created["pointer"], audience="quanthor")


def test_approval_is_bound_and_consumed_once():
    store = GatewayWebMCPStore(sqlite3.connect(":memory:"))
    digest = "a" * 64
    issued = store.issue_approval(session_token="session-a", tool_name="gateway_plan_qbit_handoff", payload_sha256=digest, idempotency_key="idem-key-00000001")
    assert store.consume_approval(issued["receipt"], session_token="session-a", tool_name="gateway_plan_qbit_handoff", payload_sha256=digest)
    assert not store.consume_approval(issued["receipt"], session_token="session-a", tool_name="gateway_plan_qbit_handoff", payload_sha256=digest)


def test_gateway_theme_explicitly_records_accessible_fallback():
    assert THEME["sourceStatus"] == "fallback-no-product-stitch-found"


def test_wsgi_page_and_manifest_are_public_but_invoke_is_not():
    pytest.importorskip("authlib")
    from fnpqnn_gateway_mvp.auth0_gateway import Auth0Config, IdentityApplication
    from fnpqnn_gateway_mvp.identity_store import IdentityStore
    identity = IdentityStore(sqlite3.connect(":memory:"))
    config = Auth0Config(issuer="", client_id="", client_secret="", audience="", callback_url="", logout_return_url="", organization_id="", allowed_return_urls=(), allowed_origins=())
    client = type("Client", (), {"ready": lambda self: False})()
    app = IdentityApplication(identity, client, config)
    def call(method, path, body=b""):
        captured = {}
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "", "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
        raw = b"".join(app(env, lambda status, headers: captured.update(status=status, headers=headers)))
        return captured["status"], dict(captured["headers"]), raw
    status, headers, page = call("GET", "/webmcp")
    assert status == "200 OK" and headers["Content-Type"].startswith("text/html") and b"Gateway WebMCP" in page
    status, _, raw = call("GET", "/api/v1/webmcp/manifest")
    assert status == "200 OK" and len(json.loads(raw)["tools"]) == 12
    status, _, raw = call("POST", "/api/v1/webmcp/invoke", json.dumps({"name": "gateway_inspect_session", "arguments": {}}).encode())
    assert status == "401 Unauthorized" and json.loads(raw)["error"] == "session_required"
