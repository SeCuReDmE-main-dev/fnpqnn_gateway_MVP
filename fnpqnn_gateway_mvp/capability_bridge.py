"""Native tool capability bridge.

The gateway does not reimplement Codex, Gemini, Ollama, Copilot, or their
plugin systems. It describes simulator capabilities in a form the selected
native tool can consume with its own skills/plugins.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from .activation import route_for_tool


SIMULATOR_CAPABILITIES = (
    "Inspect FNP-QNN simulator docs and generated AGENTS/SOUL/USER/MEMORY files.",
    "Run gateway dry-run plans before starting runtime hooks.",
    "Use simulator CLI/HTTP boundaries instead of importing simulator internals.",
    "Create gate designs as simulator artifacts, not as provider credentials.",
    "Keep dF/differentiated simulator logic distinct from generic provider context.",
)

NATIVE_TOOL_CAPABILITIES = {
    "codex": (
        "Use Codex skills and plugins available in the user's Codex environment.",
        "Use Codex repo editing, tests, docs, and code-review workflows.",
        "Create or install Codex skills through native Codex skill tooling when approved.",
    ),
    "gemini": (
        "Use Gemini or Antigravity native coding, IDE, and agent workflows.",
        "Use Google account-approved capabilities without copying secrets into the gateway.",
    ),
    "antigravity": (
        "Use Antigravity native IDE agent workflows and project context.",
        "Use Google account-approved capabilities without copying secrets into the gateway.",
        "Create or run Antigravity-native tasks while the simulator remains a separate CLI/HTTP surface.",
    ),
    "ollama": (
        "Use local Ollama model/runtime capabilities.",
        "Use local model routing without requiring cloud login unless explicitly approved.",
    ),
    "ollama-cloud": (
        "Use Ollama/OpenClaw model and local/cloud routing capabilities.",
        "Use local model selection and OpenClaw bridge behavior when approved.",
    ),
    "github-copilot": (
        "Use Copilot IDE context, completions, chat, and workspace assistance.",
        "Keep Copilot as support surface while simulator runtime remains local.",
    ),
    "agent-platform": (
        "Use external MCP/agent platform tools as the native execution surface.",
        "Expose simulator commands and gate metadata to platform agents.",
    ),
    "openclaw": (
        "Use OpenClaw-native orchestration, skills, MCP surfaces, and bridge behavior.",
        "Expose simulator commands and gate metadata without importing simulator internals into OpenClaw.",
    ),
    "codeproject-ai": (
        "Use CodeProject.AI HTTP modules as backend services.",
        "Keep native agent orchestration in the chosen IDE or agent platform.",
    ),
    "codeproject-ai-server": (
        "Use CodeProject.AI Server HTTP modules as backend services.",
        "Keep native agent orchestration in the chosen IDE or agent platform.",
    ),
    "codeproject-ai-mesh": (
        "Use CodeProject.AI mesh as backend service fabric.",
        "Keep native agent orchestration in the chosen IDE or agent platform.",
    ),
    "simulator": (
        "Use only local simulator CLI/HTTP capabilities.",
        "Keep AI-provider behavior disabled unless a later fingerprint route is accepted.",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "skill-request"


def capability_map(tool: str, workspace: str | Path = ".") -> dict[str, Any]:
    route = route_for_tool(tool)
    ws = Path(workspace).expanduser().resolve()
    return {
        "success": True,
        "tool": route.tool,
        "native_tool": route.label,
        "runtime_hook": route.runtime_hook,
        "auth_provider": route.auth_provider,
        "bridge_model": "non-absorbing capability bridge",
        "native_tool_owns": list(NATIVE_TOOL_CAPABILITIES[route.tool]),
        "simulator_owns": list(SIMULATOR_CAPABILITIES),
        "gateway_owns": [
            "fingerprint acceptance record",
            "route selection",
            "onboarding files",
            "hook command plans",
            "skill request handoff files",
        ],
        "non_absorption_rules": [
            "The simulator does not become the provider tool.",
            "The provider tool does not become the simulator.",
            "Native skills/plugins are invoked by the native tool, not reimplemented by the gateway.",
            "Simulator gate work is represented as workspace artifacts and CLI/HTTP calls.",
        ],
        "paths": {
            "activation": str(ws / ".fnpqnn_gateway" / "activation.json"),
            "skill_requests": str(ws / ".fnpqnn_gateway" / "skill_requests"),
            "agents": str(ws / "AGENTS.md"),
            "soul": str(ws / "SOUL.md"),
            "user": str(ws / "USER.md"),
            "memory": str(ws / "MEMORY.md"),
        },
    }


def skill_request(
    tool: str,
    name: str,
    goal: str,
    workspace: str | Path = ".",
    write: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Create a native-tool request for skills/plugins without executing them."""

    route = route_for_tool(tool)
    ws = Path(workspace).expanduser().resolve()
    slug = _slug(name)
    request_dir = ws / ".fnpqnn_gateway" / "skill_requests"
    json_path = request_dir / f"{slug}.json"
    md_path = request_dir / f"{slug}.md"
    payload: dict[str, Any] = {
        "success": True,
        "tool": route.tool,
        "name": name,
        "goal": goal,
        "created_at": _now(),
        "native_handoff": {
            "native_tool_must_execute_own_skills": True,
            "native_tool": route.label,
            "runtime_hook": route.runtime_hook,
            "auth_provider": route.auth_provider,
        },
        "capability_map": capability_map(route.tool, ws),
        "requested_skill_contract": {
            "purpose": goal,
            "must_use_gateway_state": True,
            "must_keep_simulator_independent": True,
            "must_not_store_raw_tokens": True,
            "expected_outputs": [
                "gate design",
                "simulator CLI/HTTP command plan",
                "tests or validation steps",
                "docs update when behavior changes",
            ],
        },
        "paths": {"json": str(json_path), "markdown": str(md_path)},
        "dry_run": not write,
    }
    markdown = (
        f"# Native Skill Request: {name}\n\n"
        f"- tool: {route.tool}\n"
        f"- native_tool: {route.label}\n"
        f"- runtime_hook: {route.runtime_hook}\n"
        f"- auth_provider: {route.auth_provider or 'none'}\n\n"
        "## Goal\n\n"
        f"{goal}\n\n"
        "## Non-Absorption Rule\n\n"
        "Use native skills/plugins from the selected tool to help the simulator. "
        "Do not merge provider internals into the simulator and do not reduce the native tool to a simulator-only shell.\n\n"
        "## Simulator Capability Surface\n\n"
        + "\n".join(f"- {item}" for item in SIMULATOR_CAPABILITIES)
        + "\n"
    )
    payload["markdown_preview"] = markdown
    if write:
        request_dir.mkdir(parents=True, exist_ok=True)
        for path, content in ((json_path, json.dumps(payload, indent=2, sort_keys=True)), (md_path, markdown)):
            if path.exists() and not force:
                continue
            path.write_text(content, encoding="utf-8")
    return payload
