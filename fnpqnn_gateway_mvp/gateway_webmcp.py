"""Fail-closed WebMCP control plane for the SecuredMe Education Gateway."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets
import sqlite3
from typing import Any

from .codeproject_contract import gateway_capabilities, gateway_health, gateway_mesh_status

SCHEMA = "securedme.webmcp.v1"
PRODUCT_SLUG = "gateway"
COMMON_TOOLS = ("securedme_companion_context", "securedme_qbit_plan_handoff")
FORBIDDEN_KEYS = ("secret", "token", "cookie", "password", "authorization", ".env", "browser_session", "client_secret", "provider_subject")
THEME = {
    "slug": PRODUCT_SLUG,
    "source": "securedme-site/theme-fallbacks/securedme-education-accessible.v1",
    "sourceStatus": "fallback-no-product-stitch-found",
    "tokens": {"background": "#071025", "surface": "#10203b", "primary": "#1f7aff", "secondary": "#6f42ff", "accent": "#d8a548", "text": "#f7fbff", "muted": "#9aa8c7", "focus": "#23b8ff"},
    "typography": {"display": "system-ui, sans-serif", "body": "system-ui, sans-serif", "code": "monospace"},
    "fallback": "SecuredMe high-contrast system theme with visible focus and no image-dependent meaning.",
}


def _object(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}


def _tool(name: str, mode: str, description: str, schema: dict[str, Any], handler: str) -> dict[str, Any]:
    return {"name": name, "title": name.replace("_", " ").title(), "description": description, "mode": mode, "availability": "available", "inputSchema": schema, "outputSchema": {"type": "object", "required": ["status", "tool", "data", "secret_values_exposed"], "properties": {"status": {"const": "success"}, "tool": {"const": name}, "data": {}, "secret_values_exposed": {"const": False}}, "additionalProperties": False}, "handler": {"kind": "local", "operation": handler.replace(" ", "_")}}


POINTER = {"pointer": {"type": "string", "minLength": 24, "maxLength": 256}, "audience": {"type": "string", "minLength": 2, "maxLength": 80}}
TOOLS = (
    _tool("gateway_inspect_session", "READ", "Inspect the current sanitized SecuredMe Education session v2.", _object(), "IdentityStore.get_session"),
    _tool("gateway_inspect_allowed_tools", "READ", "Inspect the exact allowed_tools set for the current session.", _object(), "session.allowed_tools"),
    _tool("gateway_inspect_authorization_basis", "READ", "Inspect the pseudonymous authorization basis without provider identity.", _object(), "session.authorization_basis"),
    _tool("gateway_inspect_usage", "READ", "Inspect aggregate auth usage; governance roles only.", _object(), "IdentityStore.usage_snapshot"),
    _tool("gateway_cpai_health", "READ", "Inspect the allowlisted CodeProject.AI Gateway health.", _object(), "gateway_health"),
    _tool("gateway_cpai_capabilities", "READ", "Inspect sanitized Gateway route capabilities.", _object(), "gateway_capabilities"),
    _tool("gateway_cpai_mesh_status", "READ", "Inspect sanitized mesh readiness and peer counts.", _object({"expected_peer_count": {"type": "integer", "minimum": 0, "maximum": 50}}), "gateway_mesh_status"),
    _tool("gateway_plan_qbit_handoff", "STAGE", "Prepare a source-free Qbit handoff envelope without dispatch.", _object({"mission_ref": {"type": "string", "minLength": 1, "maxLength": 120}, "artifact_refs": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 160}}}, ["mission_ref"]), "local proposal only"),
    _tool("gateway_create_opaque_pointer", "STAGE", "Create an audience-bound, sanitized opaque pointer valid for at most five minutes.", _object({"audience": {"type": "string", "minLength": 2, "maxLength": 80}, "content": {"type": "object"}, "ttl_seconds": {"type": "integer", "minimum": 30, "maximum": 300}}, ["audience", "content"]), "GatewayWebMCPStore.create_pointer"),
    _tool("gateway_resolve_opaque_pointer", "READ", "Resolve a non-expired opaque pointer for its bound audience.", _object(POINTER, ["pointer", "audience"]), "GatewayWebMCPStore.resolve_pointer"),
    _tool("securedme_companion_context", "READ", "Read the sanitized Hero Book projection carried by the session.", _object(), "session.hero_context projection"),
    _tool("securedme_qbit_plan_handoff", "STAGE", "Prepare the common Qbit return proposal without modifying progression.", _object({"mission_ref": {"type": "string", "minLength": 1, "maxLength": 120}, "artifact_refs": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 160}}}, ["mission_ref"]), "local proposal only"),
)


def manifest() -> dict[str, Any]:
    return {"schema": SCHEMA, "manifestVersion": "1.0.0", "product": {"slug": PRODUCT_SLUG, "name": "FNP-QNN Gateway", "status": "pre-alpha", "canonicalStateOwner": "algoquest", "applicationStateOwner": "gateway", "pagePatterns": ["https://gateway.securedme.ca/webmcp", "http://localhost:32173/webmcp"], "theme": THEME}, "boundaries": {"authority": "Gateway session, consent, allowed_tools and governance-role boundaries are authoritative for this surface.", "secrets": "Provider tokens, cookies, browser sessions, .env values and provider identities are forbidden.", "externalWrites": "No shell, E2B, provisioning or browser automation; pointers and approvals are one-use and expire within five minutes.", "heroProgression": "AlgoQuest alone owns Hero Book progression and evidence admission."}, "tools": list(TOOLS)}


def page_html() -> str:
    """Return the real, dependency-free Gateway discovery page."""

    return """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>SecuredMe Education Gateway WebMCP</title><style>:root{--bg:#071025;--surface:#10203b;--text:#f7fbff;--focus:#23b8ff}body{margin:0;background:var(--bg);color:var(--text);font:16px system-ui,sans-serif}main{max-width:52rem;margin:auto;padding:3rem 1.25rem}.card{background:var(--surface);border:1px solid #2b4770;padding:1.25rem;border-radius:8px}a,button{color:var(--focus)}:focus-visible{outline:3px solid var(--focus);outline-offset:3px}code{font-family:monospace}</style></head><body><main><h1>Gateway WebMCP</h1><div class=\"card\"><p>Public discovery, authenticated invocation.</p><p>Session v2, exact <code>allowed_tools</code>, one-time approvals, and audience-bound pointers are enforced server-side.</p><p id=\"status\" aria-live=\"polite\">Loading twelve descriptors...</p></div></main><script>(async()=>{const m=await fetch('/api/v1/webmcp/manifest',{credentials:'same-origin'}).then(r=>r.json());document.getElementById('status').textContent=m.tools.length+' descriptors available. Authentication is required to invoke them.';const t=m.product.theme&&m.product.theme.tokens||{};for(const[k,v]of Object.entries(t))document.documentElement.style.setProperty('--securedme-'+k,v);const api=document.modelContext;if(!api||typeof api.registerTool!=='function')return;let csrf='';try{const s=await fetch('/api/v1/session',{credentials:'same-origin'}).then(r=>r.ok?r.json():{});csrf=s.csrf_token||''}catch{}for(const d of m.tools){api.registerTool({name:d.name,description:d.description,inputSchema:d.inputSchema,execute:async(a={},c={})=>{const r=await fetch('/api/v1/webmcp/invoke',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'X-SecuredMe-WebMCP':'1'},body:JSON.stringify({name:d.name,arguments:a,nonce:c.nonce}),signal:c.signal});const p=await r.json();if(!r.ok)throw new Error(p.error_code||p.error||'WEBMCP_REJECTED');return p}})}}})();</script></body></html>"""


def tool(name: str) -> dict[str, Any] | None:
    return next((item for item in TOOLS if item["name"] == name), None)


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "<depth-limited>"
    if isinstance(value, dict):
        return {str(key): sanitize(item, depth + 1) for key, item in value.items() if not any(marker in str(key).lower() for marker in FORBIDDEN_KEYS)}
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:500]]
    if isinstance(value, str):
        return value[:20000]
    return value


class GatewayWebMCPStore:
    """Additive SQLite tables for pointers and one-time approvals."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS webmcp_pointers (
              pointer_hash TEXT PRIMARY KEY, audience TEXT NOT NULL,
              payload_json TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
              consumed_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS webmcp_approvals (
              receipt_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL, tool_name TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL, idempotency_hash TEXT NOT NULL UNIQUE,
              issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, consumed_at INTEGER
            );
            """
        )
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(webmcp_pointers)")}
        if "consumed_at" not in columns:
            self.connection.execute("ALTER TABLE webmcp_pointers ADD COLUMN consumed_at INTEGER")
        self.connection.commit()

    def create_pointer(self, content: dict[str, Any], *, audience: str, ttl_seconds: int = 300) -> dict[str, Any]:
        if not 2 <= len(audience) <= 80:
            raise ValueError("invalid pointer audience")
        safe = sanitize(content)
        encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode()) > 65536:
            raise ValueError("pointer payload exceeds 64 KiB")
        token = "ptr_" + secrets.token_urlsafe(32)
        now = _now()
        expires = now + min(max(int(ttl_seconds), 30), 300)
        self.connection.execute("INSERT INTO webmcp_pointers VALUES (?, ?, ?, ?, ?, NULL)", (_hash(token), audience, encoded, now, expires))
        self.connection.commit()
        return {"schema": "securedme.gateway.opaque-pointer.v1", "pointer": token, "audience": audience, "expires_at": expires, "raw_secret_stored": False}

    def resolve_pointer(self, pointer: str, *, audience: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM webmcp_pointers WHERE pointer_hash = ?", (_hash(pointer),)).fetchone()
        if row is None or row["consumed_at"] is not None or row["expires_at"] <= _now() or not secrets.compare_digest(row["audience"], audience):
            raise ValueError("opaque pointer is invalid, expired, or audience-mismatched")
        consumed = self.connection.execute("UPDATE webmcp_pointers SET consumed_at = ? WHERE pointer_hash = ? AND consumed_at IS NULL", (_now(), _hash(pointer))).rowcount
        self.connection.commit()
        if consumed != 1:
            raise ValueError("opaque pointer was already consumed")
        return {"schema": "securedme.gateway.opaque-pointer-result.v1", "audience": audience, "content": json.loads(row["payload_json"]), "expires_at": row["expires_at"], "one_time": True}

    def issue_approval(self, *, session_token: str, tool_name: str, payload_sha256: str, idempotency_key: str, ttl_seconds: int = 120) -> dict[str, Any]:
        if len(idempotency_key) < 16 or len(payload_sha256) != 64 or tool(tool_name) is None:
            raise ValueError("invalid approval request")
        key_hash = _hash(idempotency_key)
        existing = self.connection.execute("SELECT tool_name, payload_sha256, consumed_at FROM webmcp_approvals WHERE idempotency_hash = ?", (key_hash,)).fetchone()
        if existing:
            if existing["tool_name"] != tool_name or existing["payload_sha256"] != payload_sha256:
                raise ValueError("idempotency key was reused for another approval")
            return {"schema": "securedme.gateway.approval-receipt.v1", "status": "idempotent_replay", "receipt": None, "consumed": existing["consumed_at"] is not None}
        receipt = "approval_" + secrets.token_urlsafe(32)
        now = _now()
        expires = now + min(max(int(ttl_seconds), 30), 300)
        self.connection.execute("INSERT INTO webmcp_approvals VALUES (?, ?, ?, ?, ?, ?, ?, NULL)", (_hash(receipt), _hash(session_token), tool_name, payload_sha256, key_hash, now, expires))
        self.connection.commit()
        return {"schema": "securedme.gateway.approval-receipt.v1", "status": "issued", "receipt": receipt, "tool": tool_name, "expires_at": expires, "one_time": True}

    def consume_approval(self, receipt: str, *, session_token: str, tool_name: str, payload_sha256: str) -> bool:
        row = self.connection.execute("SELECT * FROM webmcp_approvals WHERE receipt_hash = ?", (_hash(receipt),)).fetchone()
        now = _now()
        if row is None or row["consumed_at"] is not None or row["expires_at"] <= now:
            return False
        if not (secrets.compare_digest(row["session_hash"], _hash(session_token)) and secrets.compare_digest(row["tool_name"], tool_name) and secrets.compare_digest(row["payload_sha256"], payload_sha256)):
            return False
        updated = self.connection.execute("UPDATE webmcp_approvals SET consumed_at = ? WHERE receipt_hash = ? AND consumed_at IS NULL", (now, _hash(receipt))).rowcount
        self.connection.commit()
        return updated == 1


def dispatch(name: str, arguments: dict[str, Any], session: dict[str, Any], store: GatewayWebMCPStore, identity_store: Any) -> dict[str, Any]:
    if name == "gateway_inspect_session":
        return sanitize(session)
    if name == "gateway_inspect_allowed_tools":
        return {"allowed_tools": list(session.get("allowed_tools", [])), "session_schema": session.get("schema")}
    if name == "gateway_inspect_authorization_basis":
        return {"authorization_basis": sanitize(session.get("authorization_basis", {})), "authority_ref": session.get("authority_ref"), "role": session.get("role")}
    if name == "gateway_inspect_usage":
        if session.get("role") not in {"privacy_admin", "school_admin"}:
            raise PermissionError("governance role required")
        return identity_store.usage_snapshot()
    if name == "gateway_cpai_health":
        return gateway_health()
    if name == "gateway_cpai_capabilities":
        return gateway_capabilities()
    if name == "gateway_cpai_mesh_status":
        return gateway_mesh_status(expected_peer_count=arguments.get("expected_peer_count", 11))
    if name in {"gateway_plan_qbit_handoff", "securedme_qbit_plan_handoff"}:
        return {"schema": "securedme.qbit.handoff-plan.v1", "status": "staged", "mission_ref": arguments["mission_ref"], "artifact_refs": arguments.get("artifact_refs", []), "target": "algoquest", "progression_modified": False, "dispatched": False}
    if name == "gateway_create_opaque_pointer":
        return store.create_pointer(arguments["content"], audience=arguments["audience"], ttl_seconds=arguments.get("ttl_seconds", 300))
    if name == "gateway_resolve_opaque_pointer":
        return store.resolve_pointer(arguments["pointer"], audience=arguments["audience"])
    if name == "securedme_companion_context":
        return {"schema": "HeroBookPanelState.projection.v1", "canonical_state_owner": "algoquest", "hero_context": sanitize(session.get("hero_context", {})), "revision": session.get("hero_revision"), "specialist": "gateway", "raw_learner_record_exposed": False}
    raise LookupError("registered tool has no real handler")
