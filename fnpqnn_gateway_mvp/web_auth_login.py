"""Web-auth login plans for gateway systems.

This module builds system-specific login handoffs. It is intentionally
credential-blind: no token prompt, no dotenv read, and no dotenv write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import webbrowser

from .model_provider import model_provider_switch
from .token_governor import token_governor_plan


AUTH_LOGIN_DIR = ".fnpqnn_gateway/auth_logins"


@dataclass(frozen=True)
class AuthLoginSystem:
    system: str
    label: str
    tool: str | None
    provider: str
    web_auth_target: str
    web_auth_url: str | None
    native_fallback: str
    runtime_relation: str
    support_only: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "label": self.label,
            "tool": self.tool,
            "provider": self.provider,
            "web_auth_target": self.web_auth_target,
            "web_auth_url": self.web_auth_url,
            "native_fallback": self.native_fallback,
            "runtime_relation": self.runtime_relation,
            "support_only": self.support_only,
        }


AUTH_LOGIN_SYSTEMS: dict[str, AuthLoginSystem] = {
    "natural": AuthLoginSystem(
        system="natural",
        label="Natural simulator",
        tool="simulator",
        provider="none",
        web_auth_target="none",
        web_auth_url=None,
        native_fallback="Use the local FNP-QNN simulator CLI/HTTP without external provider login.",
        runtime_relation="simulator runtime",
    ),
    "codex": AuthLoginSystem(
        system="codex",
        label="Codex / OpenAI",
        tool="codex",
        provider="openai",
        web_auth_target="Codex/OpenAI browser login",
        web_auth_url="https://chatgpt.com/auth/login",
        native_fallback="Use the installed Codex/OpenAI native login surface if browser login is unavailable.",
        runtime_relation="codex hook with simulator foreground runtime",
    ),
    "antigravity": AuthLoginSystem(
        system="antigravity",
        label="Antigravity / Gemini",
        tool="antigravity",
        provider="google",
        web_auth_target="Google/Gemini browser login",
        web_auth_url="https://accounts.google.com/",
        native_fallback="Use Antigravity, Gemini, or gcloud native login if browser login is unavailable.",
        runtime_relation="antigravity hook with simulator foreground runtime",
    ),
    "vscode": AuthLoginSystem(
        system="vscode",
        label="VS Code / GitHub Copilot",
        tool="github-copilot",
        provider="github-copilot",
        web_auth_target="GitHub/Copilot browser login",
        web_auth_url="https://github.com/login",
        native_fallback="Use VS Code Accounts or GitHub Copilot sign-in if browser login is unavailable.",
        runtime_relation="Copilot support only; simulator runtime remains local",
        support_only=True,
    ),
    "openclaw": AuthLoginSystem(
        system="openclaw",
        label="OpenClaw",
        tool="openclaw",
        provider="openclaw",
        web_auth_target="OpenClaw browser or local control-plane login",
        web_auth_url=None,
        native_fallback="Use OpenClaw native attach/login for the local control plane.",
        runtime_relation="openclaw hook with simulator foreground runtime",
    ),
    "cloud-kit": AuthLoginSystem(
        system="cloud-kit",
        label="Cloud Kit / E2B",
        tool="openclaw",
        provider="e2b",
        web_auth_target="E2B cloud browser login through the approved Cloud Kit flow",
        web_auth_url="https://e2b.dev/dashboard",
        native_fallback="Use the E2B native dashboard login if the Cloud Kit handoff cannot open a browser.",
        runtime_relation="cloud-kit preflight plus openclaw hook; E2B remains isolated compute",
    ),
    "docker-kit": AuthLoginSystem(
        system="docker-kit",
        label="Docker Kit",
        tool="simulator",
        provider="docker",
        web_auth_target="Docker Desktop or Docker Hub browser login when private images require it",
        web_auth_url="https://app.docker.com/sign-in",
        native_fallback="Use Docker Desktop native sign-in; public/local simulator images require no login.",
        runtime_relation="docker compose simulator API and Panel runtime",
    ),
    "codeproject-ai": AuthLoginSystem(
        system="codeproject-ai",
        label="CodeProject.AI Server",
        tool="codeproject-ai",
        provider="none",
        web_auth_target="none",
        web_auth_url=None,
        native_fallback="Use the local CodeProject.AI Server URL or tunnel; this is backend transport, not provider auth.",
        runtime_relation="CodeProject.AI HTTP backend with optional YOLO instruction fallback",
    ),
    "e2b": AuthLoginSystem(
        system="e2b",
        label="E2B",
        tool="openclaw",
        provider="e2b",
        web_auth_target="E2B account browser login",
        web_auth_url="https://e2b.dev/dashboard",
        native_fallback="Use the E2B dashboard login; downstream CLI state must be gateway-managed after fingerprint success.",
        runtime_relation="isolated E2B compute lane for Cloud Kit",
    ),
    "datadog": AuthLoginSystem(
        system="datadog",
        label="Datadog",
        tool="openclaw",
        provider="datadog",
        web_auth_target="Datadog browser login",
        web_auth_url="https://app.datadoghq.com/account/login",
        native_fallback="Use the Datadog account login in the browser; telemetry config remains gateway-managed after fingerprint success.",
        runtime_relation="observability account for E2B/OpenClaw audit telemetry",
    ),
    "google": AuthLoginSystem(
        system="google",
        label="Google",
        tool="antigravity",
        provider="google",
        web_auth_target="Google account browser login",
        web_auth_url="https://accounts.google.com/",
        native_fallback="Use Google native login through Gemini, Antigravity, or gcloud if browser login is unavailable.",
        runtime_relation="Gemini/Antigravity auth account",
    ),
    "github": AuthLoginSystem(
        system="github",
        label="GitHub",
        tool="github-copilot",
        provider="github",
        web_auth_target="GitHub browser login",
        web_auth_url="https://github.com/login",
        native_fallback="Use VS Code Accounts or GitHub native login if browser login is unavailable.",
        runtime_relation="GitHub/Copilot account auth",
        support_only=True,
    ),
    "docker": AuthLoginSystem(
        system="docker",
        label="Docker",
        tool="simulator",
        provider="docker",
        web_auth_target="Docker account browser login",
        web_auth_url="https://app.docker.com/sign-in",
        native_fallback="Use Docker Desktop native sign-in if browser login is unavailable.",
        runtime_relation="Docker image access for docker-kit bootstrap",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def auth_login_path(workspace: str | Path, system: str) -> Path:
    return _workspace_path(workspace) / AUTH_LOGIN_DIR / f"{system}.json"


def _system(name: str) -> AuthLoginSystem:
    normalized = name.strip().lower()
    if normalized not in AUTH_LOGIN_SYSTEMS:
        allowed = ", ".join(sorted([*AUTH_LOGIN_SYSTEMS, "all"]))
        raise ValueError(f"unknown auth login system '{name}'. Allowed systems: {allowed}")
    return AUTH_LOGIN_SYSTEMS[normalized]


def list_auth_login_systems() -> list[dict[str, Any]]:
    return [AUTH_LOGIN_SYSTEMS[name].as_dict() for name in sorted(AUTH_LOGIN_SYSTEMS)]


def validate_auth_login_plan(plan: dict[str, Any]) -> dict[str, Any]:
    system = plan.get("system", {})
    url = system.get("web_auth_url") if isinstance(system, dict) else None
    provider = system.get("provider") if isinstance(system, dict) else None
    policy = plan.get("policy", {})
    checks = {
        "https_url_or_no_provider": provider in {None, "none", "openclaw"} or (isinstance(url, str) and url.startswith("https://")),
        "no_manual_secret": not bool(policy.get("user_must_paste_secret")),
        "no_manual_env_edit": not bool(policy.get("user_must_edit_env")),
        "no_dotenv_read": not bool(policy.get("dotenv_read")),
        "no_dotenv_write": not bool(policy.get("dotenv_write")),
        "has_fingerprint_accept_command": bool(plan.get("next_commands", {}).get("accept_fingerprint")),
    }
    return {
        "success": all(checks.values()),
        "checks": checks,
        "validated_surface": "web-auth-hook-wrapper",
    }


def build_auth_login_plan(
    system: str,
    *,
    workspace: str | Path = ".",
    fingerprint: str | None = None,
    accept_fingerprint: bool = False,
    open_browser: bool = False,
) -> dict[str, Any]:
    selected = _system(system)
    ws = _workspace_path(workspace)
    accepted = bool(accept_fingerprint and fingerprint and fingerprint.strip())
    status = "fingerprint-accepted" if accepted else "pending-web-auth"
    if selected.provider == "none":
        status = "no-provider-login-required"
    browser_opened = False
    if open_browser and selected.web_auth_url:
        browser_opened = bool(webbrowser.open(selected.web_auth_url))
    provider_switch = None
    if selected.tool:
        provider_switch = model_provider_switch(
            tool=selected.tool,
            fingerprint=fingerprint or "",
            workspace=ws,
            source="web-auth" if selected.provider != "none" else "native-login",
        )
    plan = {
        "success": True,
        "created_at": _now(),
        "system": selected.as_dict(),
        "workspace": str(ws),
        "status": status,
        "fingerprint": fingerprint or "",
        "accepted": accepted,
        "auth_flow": {
            "primary": "web-auth" if selected.provider != "none" else "none",
            "fallback": "native-login",
            "last_resort": "petit-yolo-instructions",
            "web_auth_target": selected.web_auth_target,
            "web_auth_url": selected.web_auth_url,
            "native_fallback": selected.native_fallback,
            "browser_opened": browser_opened,
        },
        "web_auth_hook": {
            "name": f"{selected.system}-web-auth",
            "action": "open-browser",
            "url": selected.web_auth_url,
            "callback_contract": "provider returns a user-visible login success; gateway accepts only the resulting fingerprint string.",
            "stores_secret": False,
        },
        "policy": {
            "user_must_paste_secret": False,
            "user_must_edit_env": False,
            "dotenv_read": False,
            "dotenv_write": False,
            "managed_env_after_success_fingerprint_only": True,
            "raw_secret_stored": False,
        },
        "provider_switch": provider_switch,
        "next_commands": {
            "accept_fingerprint": (
                f"fnpqnn auth login --system {selected.system} --fingerprint <fp> "
                "--accept-fingerprint --write"
            ),
            "provider_switch": (
                f"fnpqnn function provider-switch --tool {selected.tool} --fingerprint <fp> --write"
                if selected.tool
                else "not-applicable"
            ),
            "bootstrap": (
                f"fnpqnn gateway bootstrap --profile {selected.system} --fingerprint <fp> --accept-fingerprint"
                if selected.system in {"natural", "codex", "antigravity", "vscode", "openclaw", "cloud-kit", "docker-kit"}
                else "not-applicable"
            ),
        },
        "paths": {"auth_login": str(auth_login_path(ws, selected.system))},
    }
    plan["validation"] = validate_auth_login_plan(plan)
    if selected.tool in {"codex", "antigravity", "gemini", "simulator"}:
        governor_route = selected.tool
    elif selected.system == "google":
        governor_route = "antigravity"
    else:
        governor_route = "simulator"
    plan["token_governor"] = token_governor_plan(
        route=governor_route,
        payload={
            "system": selected.as_dict(),
            "status": status,
            "auth_flow": plan["auth_flow"],
            "policy": plan["policy"],
        },
        workspace=workspace,
        activity="short_question",
        user_profile="teacher",
    )
    plan["dry_run"] = True
    return plan


def build_auth_login_all(
    *,
    workspace: str | Path = ".",
    open_browser: bool = False,
) -> dict[str, Any]:
    return {
        "success": True,
        "created_at": _now(),
        "workspace": str(_workspace_path(workspace)),
        "systems": [
            build_auth_login_plan(name, workspace=workspace, open_browser=open_browser)
            for name in sorted(AUTH_LOGIN_SYSTEMS)
        ],
        "policy": {
            "user_must_paste_secret": False,
            "user_must_edit_env": False,
            "dotenv_read": False,
            "dotenv_write": False,
        },
    }


def write_auth_login_plan(plan: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not plan.get("success"):
        return plan
    path = Path(plan["paths"]["auth_login"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return {**plan, "written": [], "skipped_existing": [str(path)]}
    path.write_text(json.dumps({**plan, "dry_run": False}, indent=2, sort_keys=True), encoding="utf-8")
    return {**plan, "dry_run": False, "written": [str(path)], "skipped_existing": []}


def auth_login(
    system: str,
    *,
    workspace: str | Path = ".",
    fingerprint: str | None = None,
    accept_fingerprint: bool = False,
    open_browser: bool = False,
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if system.strip().lower() == "all":
        return build_auth_login_all(workspace=workspace, open_browser=open_browser)
    plan = build_auth_login_plan(
        system,
        workspace=workspace,
        fingerprint=fingerprint,
        accept_fingerprint=accept_fingerprint,
        open_browser=open_browser,
    )
    if not write:
        return plan
    return write_auth_login_plan(plan, force=force)
