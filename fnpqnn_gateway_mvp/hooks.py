"""Runtime hook registry for the gateway.

Hooks describe *how the gateway observes or starts a backend*. They are not auth
providers. For example, GitHub Copilot is an auth/support provider, while
`codeproject-ai` is a runtime hook that points to a self-hosted AI server.

No hook imports FNP-QNN internals. The simulator is contacted through `fnp-qnn`
CLI commands or HTTP URLs so this repo remains independently installable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


DEFAULT_CODEPROJECT_URL = "http://localhost:32168"


@dataclass(frozen=True)
class HookSpec:
    """Decision-complete description of one backend hook.

    Attributes:
        name: CLI hook name.
        kind: Human-readable category: simulator, external-agent, or ai-server.
        description: Short help text.
        preflight: Safe commands/checks to run before execution.
        server_command: Optional command to start a local process. Keep as argv,
            never as a shell string.
        codeproject: True when this hook talks to CodeProject.AI Server.
        mesh: True when CodeProject.AI mesh diagnostics are expected.
    """

    name: str
    kind: str
    description: str
    preflight: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    server_command: tuple[str, ...] | None = None
    codeproject: bool = False
    mesh: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "preflight": [list(item) for item in self.preflight],
            "server_command": None if self.server_command is None else list(self.server_command),
            "codeproject": self.codeproject,
            "mesh": self.mesh,
        }


HOOKS: Mapping[str, HookSpec] = {
    "simulator": HookSpec(
        name="simulator",
        kind="simulator",
        description="Natural FNP-QNN simulator without external AI account hooks.",
        preflight=(("fnp-qnn", "doctor", "--no-probe-services"),),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "codex": HookSpec(
        name="codex",
        kind="external-agent",
        description="FNP-QNN simulator with Codex/OpenAI support preflight.",
        preflight=(("fnp-qnn", "support", "provider", "openai"), ("fnp-qnn", "agent", "wake-prompt", "openai")),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "gemini": HookSpec(
        name="gemini",
        kind="external-agent",
        description="FNP-QNN simulator with Gemini/Antigravity support preflight.",
        preflight=(("fnp-qnn", "support", "provider", "google"), ("fnp-qnn", "agent", "wake-prompt", "google")),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "antigravity": HookSpec(
        name="antigravity",
        kind="external-agent",
        description="FNP-QNN simulator with Antigravity/Gemini IDE support preflight.",
        preflight=(("fnp-qnn", "support", "provider", "google"), ("fnp-qnn", "agent", "wake-prompt", "antigravity")),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "agent-platform": HookSpec(
        name="agent-platform",
        kind="external-agent",
        description="OpenClaw/MCP style platform-agent preflight around FNP-QNN.",
        preflight=(("fnp-qnn", "external-ai", "inspect-openclaw"), ("fnp-qnn", "mcp", "manifest")),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "openclaw": HookSpec(
        name="openclaw",
        kind="external-agent",
        description="OpenClaw-native platform preflight around FNP-QNN.",
        preflight=(("fnp-qnn", "external-ai", "inspect-openclaw"), ("fnp-qnn", "mcp", "manifest")),
        server_command=("fnp-qnn", "operator", "api", "serve"),
    ),
    "codeproject-ai": HookSpec(
        name="codeproject-ai",
        kind="ai-server",
        description="Observe or validate one CodeProject.AI Server endpoint.",
        codeproject=True,
    ),
    "codeproject-ai-server": HookSpec(
        name="codeproject-ai-server",
        kind="ai-server",
        description="Observe or validate one CodeProject.AI Server endpoint.",
        codeproject=True,
    ),
    "codeproject-ai-mesh": HookSpec(
        name="codeproject-ai-mesh",
        kind="ai-server",
        description="Observe or validate CodeProject.AI Server mesh readiness.",
        codeproject=True,
        mesh=True,
    ),
}


def get_hook(name: str) -> HookSpec:
    if name not in HOOKS:
        allowed = ", ".join(sorted(HOOKS))
        raise ValueError(f"unknown hook '{name}'. Allowed hooks: {allowed}")
    return HOOKS[name]


def list_hooks() -> list[dict[str, object]]:
    return [HOOKS[name].as_dict() for name in sorted(HOOKS)]
