"""Persistent gateway bootstrap profiles.

Bootstrap profiles bind a user-accepted fingerprint to the concrete runtime
shape that should be reused by later `gateway start` calls. They do not store
provider secrets and they keep native tools outside the simulator runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .activation import activate, activation_plan
from .cloud_kit import DEFAULT_OPENCLAW_ENV, e2b_status, load_env_file
from .hooks import DEFAULT_CODEPROJECT_URL, get_hook
from .runner import bootstrap_dry_run_plan, run_bootstrap_plan
from .tunnel import tunnel_status


BOOTSTRAP_STATE_PATH = ".fnpqnn_gateway/bootstrap.json"


@dataclass(frozen=True)
class BootstrapProfile:
    name: str
    tool: str
    description: str
    kind: str = "python"
    codeproject_tunnel: bool = False
    cloud_kit: bool = False
    docker_kit: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "tool": self.tool,
            "description": self.description,
            "kind": self.kind,
            "codeproject_tunnel": self.codeproject_tunnel,
            "cloud_kit": self.cloud_kit,
            "docker_kit": self.docker_kit,
        }


BOOTSTRAP_PROFILES: dict[str, BootstrapProfile] = {
    "natural": BootstrapProfile(
        name="natural",
        tool="simulator",
        description="Natural simulator CLI/HTTP runtime without external AI account coupling.",
    ),
    "codex": BootstrapProfile(
        name="codex",
        tool="codex",
        description="Codex/OpenAI native handoff with simulator API foreground launch.",
    ),
    "antigravity": BootstrapProfile(
        name="antigravity",
        tool="antigravity",
        description="Antigravity/Gemini IDE handoff with simulator API foreground launch.",
    ),
    "vscode": BootstrapProfile(
        name="vscode",
        tool="github-copilot",
        description="VS Code/Copilot support route with CodeProject.AI Server tunnel diagnostics.",
        codeproject_tunnel=True,
    ),
    "openclaw": BootstrapProfile(
        name="openclaw",
        tool="openclaw",
        description="OpenClaw native platform handoff with simulator API foreground launch.",
    ),
    "cloud-kit": BootstrapProfile(
        name="cloud-kit",
        tool="openclaw",
        description="CloudKit/E2B preflight with OpenClaw route and simulator API foreground launch.",
        cloud_kit=True,
    ),
    "docker-kit": BootstrapProfile(
        name="docker-kit",
        tool="simulator",
        description="Docker compose simulator API and Panel foreground launch.",
        kind="docker",
        docker_kit=True,
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def bootstrap_state_path(workspace: str | Path) -> Path:
    return _workspace_path(workspace) / BOOTSTRAP_STATE_PATH


def _profile(name: str) -> BootstrapProfile:
    normalized = name.strip().lower()
    if normalized not in BOOTSTRAP_PROFILES:
        allowed = ", ".join(sorted(BOOTSTRAP_PROFILES))
        raise ValueError(f"unknown bootstrap profile '{name}'. Allowed profiles: {allowed}")
    return BOOTSTRAP_PROFILES[normalized]


def _docker_command() -> list[str]:
    return ["docker", "compose", "up", "--build", "simulator-api", "simulator-panel"]


def _runtime_command(hook_name: str, port: int) -> list[str] | None:
    hook = get_hook(hook_name)
    if hook.server_command:
        return [*hook.server_command, "--port", str(port)]
    return None


def _support_checks(profile: BootstrapProfile, codeproject_url: str, env_file: str | Path | None) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    if profile.codeproject_tunnel:
        checks["codeproject_tunnel"] = tunnel_status(codeproject_url, dry_run=True)
    if profile.cloud_kit:
        checks["env_file"] = load_env_file(env_file or DEFAULT_OPENCLAW_ENV)
        checks["cloud_kit"] = e2b_status()
    return checks


def build_bootstrap_plan(
    profile: str,
    fingerprint: str,
    *,
    workspace: str | Path = ".",
    accept_fingerprint: bool = False,
    port: int = 8000,
    panel_port: int = 5006,
    codeproject_url: str = DEFAULT_CODEPROJECT_URL,
    known_servers: list[str] | None = None,
    env_file: str | Path | None = None,
) -> dict[str, Any]:
    selected = _profile(profile)
    ws = _workspace_path(workspace)
    activation = activation_plan(
        selected.tool,
        fingerprint,
        workspace=ws,
        accept_fingerprint=accept_fingerprint,
        codeproject_url=codeproject_url,
        known_servers=known_servers,
    )
    hook_name = str(activation["gates"]["runtime_gate"]["hook"])
    command = _docker_command() if selected.docker_kit else _runtime_command(hook_name, port)
    return {
        "success": bool(activation["success"]),
        "accepted": bool(activation["accepted"]),
        "blocked_reason": activation.get("blocked_reason"),
        "created_at": _now(),
        "workspace": str(ws),
        "profile": selected.as_dict(),
        "activation": activation,
        "runtime_hook": hook_name,
        "command": command,
        "ports": {"api": port, "panel": panel_port},
        "codeproject_url": codeproject_url if selected.codeproject_tunnel or activation.get("codeproject_url") else None,
        "known_servers": known_servers or [],
        "env_file": str(env_file or DEFAULT_OPENCLAW_ENV) if selected.cloud_kit else None,
        "support_checks": _support_checks(selected, codeproject_url, env_file),
        "paths": {"bootstrap": str(bootstrap_state_path(ws)), "activation": activation["paths"]["activation"]},
        "mutates_config": False,
        "raw_token_stored": False,
    }


def write_bootstrap_state(plan: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not plan.get("accepted"):
        return {**plan, "dry_run": True}
    path = Path(plan["paths"]["bootstrap"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return {**plan, "written": [], "skipped_existing": [str(path)]}
    path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return {**plan, "written": [str(path)], "skipped_existing": []}


def bootstrap(
    profile: str,
    fingerprint: str,
    *,
    workspace: str | Path = ".",
    accept_fingerprint: bool = False,
    port: int = 8000,
    panel_port: int = 5006,
    codeproject_url: str = DEFAULT_CODEPROJECT_URL,
    known_servers: list[str] | None = None,
    env_file: str | Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    plan = build_bootstrap_plan(
        profile,
        fingerprint,
        workspace=workspace,
        accept_fingerprint=accept_fingerprint,
        port=port,
        panel_port=panel_port,
        codeproject_url=codeproject_url,
        known_servers=known_servers,
        env_file=env_file,
    )
    plan["dry_run"] = dry_run
    if dry_run or not plan["accepted"]:
        return plan
    activation_result = activate(
        plan["activation"]["route"]["tool"],
        fingerprint,
        workspace=workspace,
        accept_fingerprint=accept_fingerprint,
        codeproject_url=codeproject_url,
        known_servers=known_servers,
        write=True,
        force=force,
    )
    plan["activation_write"] = {
        "written": activation_result.get("written", []),
        "skipped_existing": activation_result.get("skipped_existing", []),
    }
    return write_bootstrap_state(plan, force=force)


def load_bootstrap_state(workspace: str | Path = ".") -> dict[str, Any]:
    path = bootstrap_state_path(workspace)
    if not path.exists():
        return {
            "success": False,
            "error": "bootstrap state not found",
            "path": str(path),
            "next_step": "Run fnpqnn gateway bootstrap --profile natural --fingerprint <fp> --accept-fingerprint first.",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def start_bootstrap(
    *,
    workspace: str | Path = ".",
    profile: str | None = None,
    port: int | None = None,
    codeproject_url: str | None = None,
    known_servers: list[str] | None = None,
    jsonl: bool = False,
    dry_run: bool = False,
    no_preflight: bool = False,
) -> int:
    state = load_bootstrap_state(workspace)
    if not state.get("success"):
        print(json.dumps(state, indent=2, sort_keys=True))
        return 1
    selected_profile = profile or state["profile"]["name"]
    fingerprint = state["activation"]["fingerprint"]
    plan = build_bootstrap_plan(
        selected_profile,
        fingerprint,
        workspace=workspace,
        accept_fingerprint=True,
        port=port or int(state.get("ports", {}).get("api", 8000)),
        panel_port=int(state.get("ports", {}).get("panel", 5006)),
        codeproject_url=codeproject_url or state.get("codeproject_url") or DEFAULT_CODEPROJECT_URL,
        known_servers=known_servers or state.get("known_servers") or [],
        env_file=state.get("env_file"),
    )
    if dry_run:
        print(json.dumps(bootstrap_dry_run_plan(plan), indent=2, sort_keys=True))
        return 0
    return run_bootstrap_plan(plan, jsonl=jsonl, no_preflight=no_preflight)


def list_bootstrap_profiles() -> list[dict[str, object]]:
    return [BOOTSTRAP_PROFILES[name].as_dict() for name in sorted(BOOTSTRAP_PROFILES)]
