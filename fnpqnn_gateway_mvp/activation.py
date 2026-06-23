"""Fingerprint acceptance, onboarding routing, and gate wiring.

This module is the deterministic bridge between a user's accepted login
fingerprint and the gateway path that should open next. It does not authenticate
the user itself. It records an explicit acceptance event and builds the files
and commands that let the chosen tool operate in the FNP-QNN workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .hooks import DEFAULT_CODEPROJECT_URL, HOOKS
from .natural_auth import PROVIDERS


AGENT_DOCS = ("AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md")


@dataclass(frozen=True)
class ToolRoute:
    """Decision table row for one accepted tool identity."""

    tool: str
    label: str
    auth_provider: str | None
    runtime_hook: str
    onboarding_voice: str
    wake_prompt: str
    native_surface: str
    support_only: bool = False
    codeproject: bool = False
    mesh: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "label": self.label,
            "auth_provider": self.auth_provider,
            "runtime_hook": self.runtime_hook,
            "onboarding_voice": self.onboarding_voice,
            "wake_prompt": self.wake_prompt,
            "native_surface": self.native_surface,
            "support_only": self.support_only,
            "codeproject": self.codeproject,
            "mesh": self.mesh,
        }


TOOL_ROUTES: dict[str, ToolRoute] = {
    "simulator": ToolRoute(
        tool="simulator",
        label="Natural simulator",
        auth_provider=None,
        runtime_hook="simulator",
        onboarding_voice="local-simulator",
        wake_prompt="Operate as the base FNP-QNN simulator. Keep AI optional and preserve local-first execution.",
        native_surface="FNP-QNN simulator CLI/HTTP only.",
    ),
    "codex": ToolRoute(
        tool="codex",
        label="Codex / ChatGPT",
        auth_provider="openai",
        runtime_hook="codex",
        onboarding_voice="codex-cli",
        wake_prompt="Operate through the Codex route. Use project AGENTS.md first, then gateway state, then simulator CLI/HTTP boundaries.",
        native_surface="Codex remains the native agent; the gateway exposes simulator commands, docs, and runtime hook metadata as workspace context.",
    ),
    "gemini": ToolRoute(
        tool="gemini",
        label="Gemini / Antigravity",
        auth_provider="google",
        runtime_hook="gemini",
        onboarding_voice="gemini-cli-antigravity",
        wake_prompt="Operate through the Gemini or Antigravity route. Respect the FNP-QNN workspace files and keep provider actions explicit.",
        native_surface="Gemini or Antigravity remains the native agent; the gateway exposes simulator commands, docs, and runtime hook metadata as workspace context.",
    ),
    "antigravity": ToolRoute(
        tool="antigravity",
        label="Antigravity / Gemini IDE",
        auth_provider="google",
        runtime_hook="antigravity",
        onboarding_voice="antigravity-ide",
        wake_prompt="Operate through the Antigravity route. Keep the IDE-native agent in control while exposing FNP-QNN simulator gates.",
        native_surface="Antigravity remains the native IDE agent; the gateway exposes simulator commands, docs, and gate metadata as workspace context.",
    ),
    "ollama-cloud": ToolRoute(
        tool="ollama-cloud",
        label="Ollama Cloud / OpenClaw",
        auth_provider="ollama",
        runtime_hook="ollama-cloud",
        onboarding_voice="ollama-openclaw",
        wake_prompt="Operate through the Ollama route. Prefer local/cloud model selection according to the user's approved environment.",
        native_surface="Ollama/OpenClaw remains the native agent surface; the gateway exposes simulator commands, docs, and runtime hook metadata as workspace context.",
    ),
    "ollama": ToolRoute(
        tool="ollama",
        label="Ollama local",
        auth_provider="ollama",
        runtime_hook="ollama",
        onboarding_voice="ollama-local",
        wake_prompt="Operate through the local Ollama route. Keep model execution local unless the user approves cloud routing.",
        native_surface="Ollama remains the native model/runtime surface; the gateway exposes simulator commands, docs, and runtime hook metadata as workspace context.",
    ),
    "github-copilot": ToolRoute(
        tool="github-copilot",
        label="GitHub Copilot",
        auth_provider="github-copilot",
        runtime_hook="simulator",
        onboarding_voice="copilot-ide",
        wake_prompt="Operate from the user's IDE context. Use Copilot as support/auth only; keep simulator runtime on the natural simulator hook.",
        native_surface="GitHub Copilot remains inside the IDE; the gateway exposes simulator commands and project instructions without becoming a Copilot runtime.",
        support_only=True,
    ),
    "agent-platform": ToolRoute(
        tool="agent-platform",
        label="External agent platform",
        auth_provider=None,
        runtime_hook="agent-platform",
        onboarding_voice="mcp-agent-platform",
        wake_prompt="Operate through the external agent platform gate. Keep MCP manifests and platform routing explicit.",
        native_surface="The external agent platform remains native; the gateway exposes simulator capability paths and hook metadata.",
    ),
    "openclaw": ToolRoute(
        tool="openclaw",
        label="OpenClaw",
        auth_provider=None,
        runtime_hook="openclaw",
        onboarding_voice="openclaw-agent-platform",
        wake_prompt="Operate through the OpenClaw route. Use OpenClaw-native orchestration while keeping simulator boundaries explicit.",
        native_surface="OpenClaw remains the native platform; the gateway exposes simulator capability paths, MCP-style metadata, and hook plans.",
    ),
    "codeproject-ai": ToolRoute(
        tool="codeproject-ai",
        label="CodeProject.AI Server",
        auth_provider=None,
        runtime_hook="codeproject-ai",
        onboarding_voice="codeproject-http-backend",
        wake_prompt="Operate through the CodeProject.AI HTTP backend. Treat URL, tunnel, or network access as transport, not provider login.",
        native_surface="CodeProject.AI remains an HTTP backend service; native agent takeover happens in the selected IDE/agent while this hook exposes AI server routes.",
        codeproject=True,
    ),
    "codeproject-ai-server": ToolRoute(
        tool="codeproject-ai-server",
        label="CodeProject.AI Server",
        auth_provider=None,
        runtime_hook="codeproject-ai-server",
        onboarding_voice="codeproject-http-backend",
        wake_prompt="Operate through the CodeProject.AI Server HTTP backend. Treat URL, tunnel, or network access as transport, not provider login.",
        native_surface="CodeProject.AI Server remains an HTTP backend; native agent takeover happens in the selected IDE/agent while this hook exposes AI server routes.",
        codeproject=True,
    ),
    "codeproject-ai-mesh": ToolRoute(
        tool="codeproject-ai-mesh",
        label="CodeProject.AI Server mesh",
        auth_provider=None,
        runtime_hook="codeproject-ai-mesh",
        onboarding_voice="codeproject-mesh-backend",
        wake_prompt="Operate through the CodeProject.AI mesh backend. Diagnose mesh settings and known hosts without editing server config.",
        native_surface="CodeProject.AI mesh remains a backend service; native agent takeover happens in the selected IDE/agent while this hook exposes mesh route diagnostics.",
        codeproject=True,
        mesh=True,
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def _state_paths(workspace: Path, tool: str) -> dict[str, str]:
    state = workspace / ".fnpqnn_gateway"
    return {
        "state_dir": str(state),
        "activation": str(state / "activation.json"),
        "gate": str(state / "gates" / f"{tool}.json"),
        "onboarding": str(state / "onboarding" / f"{tool}.json"),
        "wake_prompt": str(state / "prompts" / f"{tool}_wake_prompt.md"),
        "agents": str(workspace / "AGENTS.md"),
        "soul": str(workspace / "SOUL.md"),
        "user": str(workspace / "USER.md"),
        "memory": str(workspace / "MEMORY.md"),
    }


def _questions(route: ToolRoute) -> list[dict[str, str]]:
    base = [
        {"id": "mission", "question": "What is the simulator mission for this workspace?"},
        {"id": "operator_style", "question": "Should the agent act as builder, debugger, researcher, or operator?"},
        {"id": "risk_boundary", "question": "What actions must require explicit user approval?"},
        {"id": "memory_policy", "question": "What should be remembered in MEMORY.md and what must stay ephemeral?"},
    ]
    if route.auth_provider:
        base.append({"id": "provider_boundary", "question": f"What may the {route.auth_provider} login be used for in this workspace?"})
    if route.codeproject:
        base.append({"id": "backend_url", "question": "Which CodeProject.AI URL, tunnel, or mesh host is approved for this workspace?"})
    if route.support_only:
        base.append({"id": "ide_boundary", "question": "Which IDE actions can Copilot assist with while the simulator hook stays local?"})
    return base


def _agent_doc_content(route: ToolRoute, fingerprint: str, paths: dict[str, str], codeproject_url: str) -> dict[str, str]:
    header = (
        f"# FNP-QNN Gateway Activation\n\n"
        f"- tool: {route.tool}\n"
        f"- runtime_hook: {route.runtime_hook}\n"
        f"- auth_provider: {route.auth_provider or 'none'}\n"
        f"- onboarding_voice: {route.onboarding_voice}\n"
        f"- fingerprint: {fingerprint}\n"
        f"- codeproject_url: {codeproject_url if route.codeproject else 'not-applicable'}\n"
    )
    return {
        "AGENTS.md": header
        + "\n## Operating Contract\n\n"
        + route.wake_prompt
        + "\n\n## Native Takeover\n\n"
        + route.native_surface
        + "\n\nUse the gateway state files before changing runtime hooks. Keep FNP-QNN simulator logic independent from optional AI providers.\n",
        "SOUL.md": header
        + "\n## System Voice\n\n"
        + f"The active voice is `{route.onboarding_voice}`. Keep outputs aligned with this route and with the user's approved fingerprint.\n",
        "USER.md": header
        + "\n## Onboarding Questions\n\n"
        + "\n".join(f"- [{item['id']}] {item['question']}" for item in _questions(route))
        + "\n",
        "MEMORY.md": header
        + "\n## Memory Boundary\n\n"
        + "Persist only user-approved simulator preferences, route choices, native handoff boundaries, and stable workspace instructions. Do not store raw provider tokens.\n",
    }


def route_for_tool(tool: str) -> ToolRoute:
    normalized = tool.strip().lower()
    if normalized not in TOOL_ROUTES:
        allowed = ", ".join(sorted(TOOL_ROUTES))
        raise ValueError(f"unknown activation tool '{tool}'. Allowed tools: {allowed}")
    route = TOOL_ROUTES[normalized]
    if route.runtime_hook not in HOOKS:
        raise ValueError(f"route '{route.tool}' points to missing hook '{route.runtime_hook}'")
    if route.auth_provider is not None and route.auth_provider not in PROVIDERS:
        raise ValueError(f"route '{route.tool}' points to missing auth provider '{route.auth_provider}'")
    return route


def activation_plan(
    tool: str,
    fingerprint: str,
    workspace: str | Path = ".",
    accept_fingerprint: bool = False,
    codeproject_url: str = DEFAULT_CODEPROJECT_URL,
    known_servers: list[str] | None = None,
) -> dict[str, Any]:
    """Build the complete gate plan without writing files."""

    route = route_for_tool(tool)
    ws = _workspace_path(workspace)
    paths = _state_paths(ws, route.tool)
    accepted = bool(accept_fingerprint and fingerprint.strip())
    gate_command = ["fnpqnn", "gateway", "run", "--hook", route.runtime_hook]
    if route.codeproject:
        gate_command.extend(["--codeproject-url", codeproject_url])
    for known_server in known_servers or []:
        gate_command.extend(["--known-server", known_server])
    return {
        "success": accepted,
        "accepted": accepted,
        "blocked_reason": None if accepted else "Fingerprint must be provided and explicitly accepted.",
        "fingerprint": fingerprint,
        "workspace": str(ws),
        "route": route.as_dict(),
        "paths": paths,
        "gates": {
            "login_gate": {
                "provider": route.auth_provider,
                "required": route.auth_provider is not None,
                "support_only": route.support_only,
            },
            "fingerprint_gate": {"accepted": accepted, "stores_secret": False},
            "onboarding_gate": {
                "voice": route.onboarding_voice,
                "questions": _questions(route),
                "writes": [paths["agents"], paths["soul"], paths["user"], paths["memory"]],
            },
            "runtime_gate": {
                "hook": route.runtime_hook,
                "command": gate_command,
                "support_only": route.support_only,
            },
            "native_handoff_gate": {
                "agent_stays_native": True,
                "native_surface": route.native_surface,
                "simulator_capabilities": [
                    "fnpqnn gateway hooks",
                    "fnpqnn gateway doctor --hook " + route.runtime_hook,
                    "fnpqnn gateway run --hook " + route.runtime_hook + " --dry-run",
                    "workspace AGENTS.md/SOUL.md/USER.md/MEMORY.md",
                    ".fnpqnn_gateway/activation.json",
                ],
            },
        },
        "codeproject_url": codeproject_url if route.codeproject else None,
        "known_servers": known_servers or [],
        "created_at": _now(),
    }


def activate(
    tool: str,
    fingerprint: str,
    workspace: str | Path = ".",
    accept_fingerprint: bool = False,
    codeproject_url: str = DEFAULT_CODEPROJECT_URL,
    known_servers: list[str] | None = None,
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Build or write activation state for the selected route."""

    plan = activation_plan(
        tool=tool,
        fingerprint=fingerprint,
        workspace=workspace,
        accept_fingerprint=accept_fingerprint,
        codeproject_url=codeproject_url,
        known_servers=known_servers,
    )
    plan["dry_run"] = not write
    if not plan["accepted"] or not write:
        return plan

    route = route_for_tool(tool)
    paths = {name: Path(value) for name, value in plan["paths"].items()}
    written: list[str] = []
    skipped: list[str] = []
    for key in ("state_dir",):
        paths[key].mkdir(parents=True, exist_ok=True)
    for key in ("gate", "onboarding", "wake_prompt"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)

    gate_payload = json.dumps(plan["gates"], indent=2, sort_keys=True)
    onboarding_payload = json.dumps({"voice": route.onboarding_voice, "questions": _questions(route)}, indent=2, sort_keys=True)
    write_map = {
        paths["activation"]: json.dumps(plan, indent=2, sort_keys=True),
        paths["gate"]: gate_payload,
        paths["onboarding"]: onboarding_payload,
        paths["wake_prompt"]: route.wake_prompt + "\n",
    }
    write_map.update({Path(plan["paths"][name.removesuffix(".md").lower()]): content for name, content in _agent_doc_content(route, fingerprint, plan["paths"], codeproject_url).items()})

    for path, content in write_map.items():
        if path.exists() and not force:
            skipped.append(str(path))
            continue
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    plan["written"] = written
    plan["skipped_existing"] = skipped
    return plan


def list_activation_routes() -> list[dict[str, object]]:
    return [TOOL_ROUTES[name].as_dict() for name in sorted(TOOL_ROUTES)]
