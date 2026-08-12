"""Refuse Auth0 mutation unless the tenant is Development and synthetic-only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib import parse, request


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required setting: {name}")
    return value


def api_json(url: str, token: str) -> object:
    req = request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with request.urlopen(req, timeout=15) as response:
        return json.load(response)


def management_token(domain: str) -> str:
    body = parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": require("AUTH0_DEPLOY_CLIENT_ID"),
        "client_secret": require("AUTH0_DEPLOY_CLIENT_SECRET"),
        "audience": f"https://{domain}/api/v2/",
    }).encode()
    req = request.Request(f"https://{domain}/oauth/token", data=body, method="POST",
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
    with request.urlopen(req, timeout=15) as response:
        return str(json.load(response)["access_token"])


def main() -> int:
    if os.environ.get("AUTH0_TENANT_ENVIRONMENT") != "Development":
        raise RuntimeError("tenant must be explicitly marked Development")
    if os.environ.get("AUTH0_ALLOW_DELETE", "false").lower() != "false":
        raise RuntimeError("AUTH0_ALLOW_DELETE must remain false")
    domain = require("AUTH0_DOMAIN").removeprefix("https://").rstrip("/")
    token = management_token(domain)
    users = api_json(f"https://{domain}/api/v2/users?per_page=100&include_totals=true", token)
    organizations = api_json(f"https://{domain}/api/v2/organizations?per_page=100", token)
    user_items = users.get("users", []) if isinstance(users, dict) else users
    unsafe_users = [item for item in user_items if not item.get("app_metadata", {}).get("securedme_synthetic")]
    unsafe_orgs = [item for item in organizations if item.get("name") != "securedme-synthetic-school"]
    if unsafe_users or unsafe_orgs:
        raise RuntimeError("tenant contains non-synthetic users or unrelated organizations")
    result = {
        "schema": "auth0_entitlement_snapshot.v1",
        "tenant_environment": "Development",
        "synthetic_user_count": len(user_items),
        "organization_count": len(organizations),
        "safe_to_dry_run": True,
        "contains_pii": False,
    }
    output = Path(__file__).parents[1] / "snapshots" / "preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"preflight blocked: {exc}", file=sys.stderr)
        raise SystemExit(2)
