"""Model provider routing for accepted fingerprints.

Provider switching is web-auth first. The gateway never asks the user to paste
secrets or edit dotenv files; any managed environment state is allowed only as
an automatic result of a successful web-auth fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .activation import route_for_tool
from .bootstrap import load_bootstrap_state
from .natural_auth import copilot_status, provider_status


MODEL_PROVIDER_STATE_PATH = ".fnpqnn_gateway/model_provider.json"
AUTH_SOURCE_PRIORITY = ("web-auth", "native-login", "petit-yolo-instructions")


@dataclass(frozen=True)
class ProviderRoute:
    provider: str
    model_provider: str
    default_auth_source: str
    web_auth_instruction: str
    native_login_instruction: str
    instructions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_provider": self.model_provider,
            "default_auth_source": self.default_auth_source,
            "web_auth_instruction": self.web_auth_instruction,
            "native_login_instruction": self.native_login_instruction,
            "instructions": list(self.instructions),
        }


PROVIDER_ROUTES: dict[str, ProviderRoute] = {
    "openai": ProviderRoute(
        provider="openai",
        model_provider="openai",
        default_auth_source="web-auth",
        web_auth_instruction="Open the Codex/OpenAI browser login and accept the returned fingerprint.",
        native_login_instruction="Use the installed Codex/OpenAI native login surface if web auth is unavailable.",
        instructions=("Do not ask for secrets. Managed env state may be built only after a successful web-auth fingerprint.",),
    ),
    "google": ProviderRoute(
        provider="google",
        model_provider="gemini",
        default_auth_source="web-auth",
        web_auth_instruction="Open the Google/Gemini browser login and accept the returned fingerprint.",
        native_login_instruction="Use Gemini, Antigravity, or gcloud native login if web auth is unavailable.",
        instructions=("Do not ask for secrets. Managed env state may be built only after a successful web-auth fingerprint.",),
    ),
    "github-copilot": ProviderRoute(
        provider="github-copilot",
        model_provider="github-copilot",
        default_auth_source="web-auth",
        web_auth_instruction="Open GitHub/Copilot browser login and accept the returned fingerprint.",
        native_login_instruction="Use VS Code Accounts/Copilot sign-in if web auth is unavailable.",
        instructions=("Do not ask for secrets. Copilot remains an IDE support provider, not a runtime hook.",),
    ),
    "none": ProviderRoute(
        provider="none",
        model_provider="simulator",
        default_auth_source="native-login",
        web_auth_instruction="No provider web auth is required.",
        native_login_instruction="Use the local simulator without external provider login.",
        instructions=("No external model provider is required for this fingerprint route.",),
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def model_provider_state_path(workspace: str | Path) -> Path:
    return _workspace_path(workspace) / MODEL_PROVIDER_STATE_PATH


def _native_signal(provider: str) -> dict[str, Any] | None:
    if provider == "github-copilot":
        return copilot_status("auto").get("signals", {})
    return None


def _source_available(source: str, provider_route: ProviderRoute, auth_status: dict[str, Any]) -> bool:
    if source == "web-auth":
        return provider_route.provider != "none"
    if source == "native-login":
        return bool(auth_status.get("success", True))
    if source == "petit-yolo-instructions":
        return True
    return False


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    aliases = {
        "web": "web-auth",
        "browser": "web-auth",
        "native": "native-login",
        "yolo": "petit-yolo-instructions",
        "instructions": "petit-yolo-instructions",
    }
    return aliases.get(normalized, normalized)


def _select_source(provider_route: ProviderRoute, auth_status: dict[str, Any], preferred_source: str) -> tuple[str, list[str]]:
    normalized = _normalize_source(preferred_source)
    if normalized != "auto":
        return normalized, ["explicit source requested"]

    reasons: list[str] = []
    for source in AUTH_SOURCE_PRIORITY:
        if _source_available(source, provider_route, auth_status):
            reasons.append(f"{source} available")
            return source, reasons
        reasons.append(f"{source} unavailable")
    return provider_route.default_auth_source, reasons


def _safe_auth_status(provider: str, provider_route: ProviderRoute) -> dict[str, Any]:
    if provider == "none":
        return {"success": True, "provider": "none", "raw_token_stored": False, "instructions": list(provider_route.instructions)}
    status = dict(provider_status(provider))
    status["instructions"] = [
        provider_route.web_auth_instruction,
        provider_route.native_login_instruction,
        *provider_route.instructions,
    ]
    status["raw_token_stored"] = False
    status["manual_secret_required"] = False
    return status


def _resolve_tool_from_last(workspace: str | Path) -> tuple[str | None, str | None, dict[str, Any] | None]:
    state = load_bootstrap_state(workspace)
    if not state.get("success"):
        return None, None, state
    profile = state.get("profile", {})
    activation = state.get("activation", {})
    tool = str(profile.get("tool") or activation.get("route", {}).get("tool") or "")
    fingerprint = str(activation.get("fingerprint") or "")
    return tool, fingerprint, state


def build_model_provider_switch(
    *,
    tool: str | None = None,
    fingerprint: str | None = None,
    workspace: str | Path = ".",
    last: bool = False,
    source: str = "auto",
) -> dict[str, Any]:
    selected_tool = tool
    selected_fingerprint = fingerprint
    bootstrap_state: dict[str, Any] | None = None

    if last:
        selected_tool, selected_fingerprint, bootstrap_state = _resolve_tool_from_last(workspace)
        if not selected_tool:
            return {
                "success": False,
                "error": "bootstrap state not found",
                "bootstrap_state": bootstrap_state,
                "next_step": "Run fnpqnn gateway bootstrap --profile <profile> --fingerprint <fp> --accept-fingerprint first, or pass --tool and --fingerprint.",
            }

    if not selected_tool:
        raise ValueError("provider switch requires --tool or --last")

    route = route_for_tool(selected_tool)
    provider_name = route.auth_provider or "none"
    provider_route = PROVIDER_ROUTES[provider_name]
    auth_status = _safe_auth_status(provider_name, provider_route)
    selected_source, source_reasons = _select_source(provider_route, auth_status, source)
    ws = _workspace_path(workspace)
    state_path = model_provider_state_path(ws)
    return {
        "success": True,
        "created_at": _now(),
        "workspace": str(ws),
        "fingerprint": selected_fingerprint or fingerprint or "",
        "tool": route.tool,
        "runtime_hook": route.runtime_hook,
        "support_only": route.support_only,
        "provider": provider_route.as_dict(),
        "selected_auth_source": selected_source,
        "source_reasons": source_reasons,
        "auth_status": auth_status,
        "auth_signals": {
            "web_auth_required": provider_name != "none",
            "native": _native_signal(provider_name),
            "secret_values_included": False,
        },
        "managed_env_policy": {
            "user_must_edit_env": False,
            "user_must_paste_token": False,
            "dotenv_read_for_switch": False,
            "dotenv_write_allowed_after_fingerprint": True,
            "dotenv_owner": "gateway-managed-after-web-auth-success",
        },
        "fallback": {
            "name": "petit-yolo-instructions",
            "when": "Use only when web auth and native login are unavailable.",
            "instruction": "Run a small YOLO/instruction pass that tells the operator which provider web login to open, without requesting secrets or .env edits.",
            "command": "fnpqnn codeproject yolo-status --dry-run",
        },
        "commands": {
            "start": f"fnpqnn gateway start --workspace {ws}",
            "run_dry": f"fnpqnn gateway run --hook {route.runtime_hook} --dry-run",
            "status": f"fnpqnn auth provider-status {provider_name}" if provider_name != "none" else "fnpqnn gateway doctor --hook simulator",
        },
        "paths": {"model_provider": str(state_path)},
        "bootstrap_source": "last" if last else "explicit",
        "raw_token_stored": False,
        "mutates_provider_config": False,
    }


def write_model_provider_switch(plan: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not plan.get("success"):
        return plan
    path = Path(plan["paths"]["model_provider"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return {**plan, "written": [], "skipped_existing": [str(path)]}
    path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return {**plan, "written": [str(path)], "skipped_existing": []}


def model_provider_switch(
    *,
    tool: str | None = None,
    fingerprint: str | None = None,
    workspace: str | Path = ".",
    last: bool = False,
    source: str = "auto",
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    plan = build_model_provider_switch(tool=tool, fingerprint=fingerprint, workspace=workspace, last=last, source=source)
    plan["dry_run"] = not write
    if not write:
        return plan
    return write_model_provider_switch(plan, force=force)


def list_model_provider_routes() -> list[dict[str, Any]]:
    return [PROVIDER_ROUTES[name].as_dict() for name in sorted(PROVIDER_ROUTES)]
