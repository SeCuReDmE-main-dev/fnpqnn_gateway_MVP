"""Provision five synthetic Auth0 users and their internal SecuredMe assignments."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from urllib import error, parse, request

repo_root = Path(__file__).parents[3]
sys.path.insert(0, str(repo_root))

from fnpqnn_gateway_mvp.identity_store import IdentityStore

from preflight import api_json, management_token, require


def write_json(url: str, token: str, payload: dict, method: str = "POST") -> object:
    req = request.Request(url, data=json.dumps(payload).encode(), method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json",
    })
    with request.urlopen(req, timeout=15) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def find_or_create_user(domain: str, token: str, email: str, password: str, persona: str, connection: str) -> dict:
    query = parse.quote(f'email:"{email}"')
    users = api_json(f"https://{domain}/api/v2/users?q={query}&search_engine=v3", token)
    if users:
        user = users[0]
        if not user.get("app_metadata", {}).get("securedme_synthetic"):
            raise RuntimeError(f"existing account for {persona} is not marked synthetic")
        return user
    return write_json(f"https://{domain}/api/v2/users", token, {
        "connection": connection, "email": email, "password": password, "email_verified": True,
        "verify_email": False, "app_metadata": {"securedme_synthetic": True, "persona": persona},
    })


def main() -> int:
    if os.environ.get("SECUREDME_AUTH0_PERSONA_CONFIRMATION") != "CREATE_FIVE_SYNTHETIC_PERSONAS":
        raise RuntimeError("explicit synthetic-persona confirmation is required")
    if os.environ.get("AUTH0_TENANT_ENVIRONMENT") != "Development":
        raise RuntimeError("personas may be provisioned only in a Development tenant")
    domain = require("AUTH0_DOMAIN").removeprefix("https://").rstrip("/")
    token = management_token(domain)
    organizations = api_json(f"https://{domain}/api/v2/organizations?name=securedme-synthetic-school", token)
    if len(organizations) != 1:
        raise RuntimeError("securedme-synthetic-school organization must exist exactly once")
    organization_id = organizations[0]["id"]
    authority_ref = "authority_" + hashlib.sha256(organization_id.encode()).hexdigest()[:20]
    connection = os.environ.get("AUTH0_SYNTHETIC_CONNECTION", "Username-Password-Authentication")
    connections = api_json(
        f"https://{domain}/api/v2/connections?name={parse.quote(connection)}&strategy=auth0", token
    )
    if len(connections) != 1:
        raise RuntimeError("the synthetic database connection must exist exactly once")
    connection_id = connections[0]["id"]
    enabled_connections = api_json(
        f"https://{domain}/api/v2/organizations/{organization_id}/enabled_connections", token
    )
    if not any(item.get("connection_id") == connection_id for item in enabled_connections):
        write_json(f"https://{domain}/api/v2/organizations/{organization_id}/enabled_connections", token, {
            "connection_id": connection_id,
            "assign_membership_on_login": False,
            "is_signup_enabled": False,
            "show_as_button": True,
        })
    manifest = json.loads((Path(__file__).parents[1] / "synthetic-personas.json").read_text(encoding="utf-8"))
    identity_db = Path(require("SECUREDME_IDENTITY_DB"))
    if not identity_db.is_absolute():
        identity_db = repo_root / identity_db
    identity_db.parent.mkdir(parents=True, exist_ok=True)
    store = IdentityStore.from_path(str(identity_db))
    provisioned = []
    for persona in manifest["personas"]:
        email, password = require(persona["email_env"]), require(persona["password_env"])
        user = find_or_create_user(domain, token, email, password, persona["key"], connection)
        try:
            write_json(f"https://{domain}/api/v2/organizations/{organization_id}/members", token,
                       {"members": [user["user_id"]]})
        except error.HTTPError as exc:
            if exc.code != 409:
                raise
        identity = store.resolve_identity(issuer=f"https://{domain}/", provider_subject=user["user_id"])
        store.assign_role(
            securedme_id=identity["securedme_id"], authority_ref=authority_ref,
            role=persona["internal_role"], age_band="16-24" if persona["key"].startswith("student") else "adult-or-staff",
            consent_scope="suite", allowed_tools=["algoquest", "synthia"],
            subject_ref=persona.get("subject_ref", ""), assigned_class_refs=persona.get("assigned_class_refs", []),
        )
        provisioned.append(persona["key"])
    print(json.dumps({"provisioned": provisioned, "contains_pii": False, "raw_secret_stored": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
