"""Native web-search/deepsearch skill contracts.

The gateway does not scrape by default. It routes the simulator deepsearch
skill to the provider-native search surface selected by the user's authlog,
then falls back to Antigravity/Gemini when the selected provider has no
declared native web-search route. Ollama Cloud is not an official school
provider route.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .skill_creator import normalize_skill_name
from .web_auth_login import AUTH_LOGIN_DIR, AUTH_LOGIN_SYSTEMS, auth_login, auth_login_path


DEEPSEARCH_DIR = ".fnpqnn_gateway/deepsearch"
DEEPSEARCH_SKILL_NAME = "native-web-search"

NATIVE_WEB_SEARCH_ROUTES: dict[str, dict[str, Any]] = {
    "google": {
        "route": "antigravity-gemini-google-search",
        "provider": "google",
        "system": "antigravity",
        "runtime_hook": "antigravity",
        "strategy": "Use Gemini/Antigravity native Google-auth web search or grounding.",
        "provider_native_available": True,
    },
}

FALLBACK_WEB_SEARCH_ROUTE: dict[str, Any] = {
    "route": "antigravity-gemini-google-search",
    "provider": "google",
    "system": "antigravity",
    "runtime_hook": "antigravity",
    "strategy": "Selected provider has no declared native web-search route; fall back to Gemini/Antigravity native Google-auth search.",
    "provider_native_available": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def _deepsearch_slug(query: str) -> str:
    try:
        base = normalize_skill_name(query)
    except ValueError:
        base = "query"
    return normalize_skill_name(f"deepsearch-{base}")[:63].rstrip("-")


def _auth_login_dir(workspace: str | Path) -> Path:
    return _workspace_path(workspace) / AUTH_LOGIN_DIR


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_written_authlog(workspace: str | Path, system: str) -> dict[str, Any] | None:
    path = auth_login_path(workspace, system)
    if not path.exists():
        return None
    payload = _read_json(path)
    payload.setdefault("paths", {})["auth_login"] = str(path)
    return payload


def _load_last_authlog(workspace: str | Path) -> dict[str, Any] | None:
    auth_dir = _auth_login_dir(workspace)
    if not auth_dir.exists():
        return None
    candidates = sorted(auth_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    payload = _read_json(candidates[0])
    payload.setdefault("paths", {})["auth_login"] = str(candidates[0])
    return payload


def _resolve_authlog(
    *,
    workspace: str | Path,
    system: str | None,
    last_auth: bool,
    fingerprint: str | None,
) -> dict[str, Any]:
    if last_auth:
        payload = _load_last_authlog(workspace)
        if payload is None:
            return {
                "success": False,
                "error": "authlog state not found",
                "next_step": "Run fnpqnn auth login --system <system> --fingerprint <fp> --accept-fingerprint --write, then rerun with --last-auth.",
            }
        return {"success": True, "source": "last-auth", "authlog": payload}

    if not system:
        return {
            "success": False,
            "error": "deepsearch requires --last-auth or --system <system>",
            "next_step": "Use --last-auth to reuse the latest accepted authlog, or pass --system google/antigravity.",
        }

    selected = system.strip().lower()
    if selected not in AUTH_LOGIN_SYSTEMS:
        allowed = ", ".join(sorted(AUTH_LOGIN_SYSTEMS))
        raise ValueError(f"unknown auth login system '{system}'. Allowed systems: {allowed}")

    payload = _load_written_authlog(workspace, selected)
    if payload is not None:
        return {"success": True, "source": "written-authlog", "authlog": payload}

    planned = auth_login(selected, workspace=workspace, fingerprint=fingerprint, accept_fingerprint=bool(fingerprint))
    return {"success": True, "source": "planned-authlog", "authlog": planned}


def _authlog_system(authlog: dict[str, Any]) -> dict[str, Any]:
    system = authlog.get("system", {})
    if not isinstance(system, dict):
        return {}
    return system


def _route_for_authlog(authlog: dict[str, Any]) -> dict[str, Any]:
    system = _authlog_system(authlog)
    provider = str(system.get("provider") or "none").lower()
    route = dict(NATIVE_WEB_SEARCH_ROUTES.get(provider, FALLBACK_WEB_SEARCH_ROUTE))
    route["selected_provider"] = provider
    route["selected_system"] = str(system.get("system") or "")
    route["fallback_used"] = provider not in NATIVE_WEB_SEARCH_ROUTES
    return route


def _deepsearch_paths(workspace: str | Path, slug: str) -> dict[str, str]:
    base = _workspace_path(workspace) / DEEPSEARCH_DIR
    return {
        "contract_json": str(base / f"{slug}.json"),
        "contract_markdown": str(base / f"{slug}.md"),
    }


def _skill_md_template(payload: dict[str, Any]) -> str:
    route = payload["search_route"]
    return (
        "---\n"
        f"name: {DEEPSEARCH_SKILL_NAME}\n"
        "description: Route simulator research requests to provider-native web search based on the accepted authlog session, gather and filter cited evidence, and produce a report without scraping or storing secrets.\n"
        "---\n\n"
        "# Native Web Search\n\n"
        "Use this skill when a simulator user asks to validate research, run web search, or build a deepsearch report.\n\n"
        "## Workflow\n\n"
        "1. Read the gateway deepsearch contract JSON.\n"
        f"2. Use route `{route['route']}` for the selected authlog provider.\n"
        "3. Gather results through the provider-native search surface; do not build a generic scraper first.\n"
        "4. Filter by relevance, credibility, duplication, and recency where requested.\n"
        "5. Produce a report with citations, provider route, caveats, and validation status.\n"
        "6. Never store tokens, cookies, API keys, or browser session secrets in the report or contract.\n"
    )


def _markdown_contract(payload: dict[str, Any]) -> str:
    route = payload["search_route"]
    authlog = payload["authlog"]
    system = _authlog_system(authlog)
    return (
        f"# Deepsearch Skill: {payload['slug']}\n\n"
        f"- query: {payload['query']}\n"
        f"- research_goal: {payload['research_goal']}\n"
        f"- authlog_source: {payload['authlog_source']}\n"
        f"- selected_system: {system.get('system', '')}\n"
        f"- selected_provider: {route['selected_provider']}\n"
        f"- search_route: {route['route']}\n"
        f"- fallback_used: {route['fallback_used']}\n"
        f"- fingerprint_ref: {payload['fingerprint_ref']}\n"
        f"- raw_secret_stored: {payload['raw_secret_stored']}\n\n"
        "## Pipeline\n\n"
        + "\n".join(f"- {step['stage']}: {step['instruction']}" for step in payload["pipeline"])
        + "\n\n## Skill.md Template\n\n"
        "```markdown\n"
        + payload["simulator_skill"]["skill_md_template"]
        + "\n```\n"
    )


def build_deepsearch_skill(
    *,
    query: str,
    research_goal: str | None = None,
    workspace: str | Path = ".",
    system: str | None = None,
    last_auth: bool = False,
    fingerprint: str | None = None,
) -> dict[str, Any]:
    resolved = _resolve_authlog(workspace=workspace, system=system, last_auth=last_auth, fingerprint=fingerprint)
    if not resolved.get("success"):
        return resolved
    authlog = resolved["authlog"]
    route = _route_for_authlog(authlog)
    system_payload = _authlog_system(authlog)
    slug = _deepsearch_slug(query)
    paths = _deepsearch_paths(workspace, slug)
    fingerprint_ref = str(authlog.get("fingerprint") or fingerprint or "")
    payload: dict[str, Any] = {
        "success": True,
        "created_at": _now(),
        "slug": slug,
        "query": query,
        "research_goal": research_goal or query,
        "workspace": str(_workspace_path(workspace)),
        "authlog_source": resolved["source"],
        "authlog": {
            "system": system_payload,
            "status": authlog.get("status", "unknown"),
            "accepted": bool(authlog.get("accepted")),
            "fingerprint_present": bool(fingerprint_ref),
            "path": authlog.get("paths", {}).get("auth_login", ""),
        },
        "fingerprint_ref": fingerprint_ref,
        "search_route": route,
        "pipeline": [
            {
                "stage": "gather",
                "instruction": "Call the provider-native web-search surface declared by search_route and collect URLs, titles, snippets, dates, and provider result IDs.",
            },
            {
                "stage": "filter",
                "instruction": "Deduplicate results, reject weak or off-topic sources, prefer primary/current sources, and keep unsupported claims out of the final report.",
            },
            {
                "stage": "report",
                "instruction": "Create a cited report with source list, provider route, fallback status, caveats, and validation result.",
            },
        ],
        "simulator_contract": {
            "entry_command": "fnpqnn function deepsearch --query <query> --last-auth --write",
            "execution_owner": "selected provider native web-search surface",
            "simulator_role": "prepare and consume the research contract; do not become the provider auth store",
            "fallback_rule": "if selected provider has no declared native web-search route, use antigravity-gemini-google-search",
        },
        "simulator_skill": {
            "name": DEEPSEARCH_SKILL_NAME,
            "skill_md_template": "",
            "required_outputs": [
                "cited research report",
                "source list with URLs or provider result IDs",
                "filter notes and caveats",
                "validation status",
            ],
        },
        "policy": {
            "no_generic_scraper_first": True,
            "no_secret_storage": True,
            "no_dotenv_read": True,
            "no_dotenv_write": True,
            "no_cookie_export": True,
            "raw_secret_stored": False,
        },
        "paths": paths,
        "raw_secret_stored": False,
        "dry_run": True,
    }
    payload["simulator_skill"]["skill_md_template"] = _skill_md_template(payload)
    payload["markdown_preview"] = _markdown_contract(payload)
    return payload


def write_deepsearch_skill(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not payload.get("success"):
        return payload
    written: list[str] = []
    skipped: list[str] = []
    paths = payload["paths"]
    serializable = {key: value for key, value in payload.items() if key != "markdown_preview"}
    for target, content in (
        (paths["contract_json"], json.dumps({**serializable, "dry_run": False}, indent=2, sort_keys=True)),
        (paths["contract_markdown"], payload["markdown_preview"]),
    ):
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            skipped.append(str(path))
            continue
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return {**payload, "dry_run": False, "written": written, "skipped_existing": skipped}
