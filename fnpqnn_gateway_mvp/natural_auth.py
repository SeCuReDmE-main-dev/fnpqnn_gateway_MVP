"""Natural auth discovery for external developer tools.

Natural auth means the user signs in through the original tool or IDE. This
module detects safe status signals and prints instructions. It does not scrape
VS Code, keychains, browser cookies, or extension secrets.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any


PROVIDERS = ("openai", "google", "github-copilot")
TOKEN_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"(Token:\s+).+", re.IGNORECASE),
)


def _sanitize(text: str) -> str:
    cleaned = text
    for pattern in TOKEN_PATTERNS:
        if pattern.pattern.startswith("(Token"):
            cleaned = pattern.sub(r"\1<redacted>", cleaned)
        else:
            cleaned = pattern.sub("<redacted-token>", cleaned)
    return cleaned


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _run(argv: tuple[str, ...], timeout: int = 15) -> dict[str, Any]:
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)
        return {"available": True, "returncode": proc.returncode, "stdout": _sanitize(proc.stdout[-2000:]), "stderr": _sanitize(proc.stderr[-2000:])}
    except FileNotFoundError:
        return {"available": False, "returncode": None, "stdout": "", "stderr": "command not found"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def copilot_status(source: str = "auto") -> dict[str, Any]:
    """Return a GitHub Copilot natural-auth report.

    `source=vscode` returns instructions only. `source=copilot-cli` and
    `source=gh` inspect command availability and auth state without reading
    tokens.
    """

    source = source.strip().lower()
    if source not in {"auto", "vscode", "copilot-cli", "gh"}:
        raise ValueError("source must be one of: auto, vscode, copilot-cli, gh")
    report: dict[str, Any] = {
        "success": True,
        "provider": "github-copilot",
        "source": source,
        "raw_token_stored": False,
        "secret_storage_read": False,
        "instructions": [],
        "signals": {},
    }
    if source in {"auto", "vscode"}:
        report["instructions"].append(
            "In VS Code, use the Copilot status/menu, Accounts menu, or Command Palette command `GitHub Copilot: Sign in`."
        )
        report["instructions"].append("After IDE sign-in, run `fnpqnn auth provider-status github-copilot`.")
    if source in {"auto", "copilot-cli"}:
        report["signals"]["copilot_cli_present"] = _command_exists("copilot")
        report["signals"]["copilot_help"] = _run(("copilot", "help")) if _command_exists("copilot") else None
        report["instructions"].append("For Copilot CLI, run `copilot`, then `/login`, and approve the browser flow.")
    if source in {"auto", "gh"}:
        report["signals"]["gh_present"] = _command_exists("gh")
        report["signals"]["gh_auth_status"] = _run(("gh", "auth", "status")) if _command_exists("gh") else None
        report["instructions"].append("If GitHub CLI is authenticated, Copilot CLI can use it as a fallback when no higher-priority credential exists.")
    report["signals"]["env_present"] = {
        "COPILOT_GITHUB_TOKEN": bool(os.environ.get("COPILOT_GITHUB_TOKEN")),
        "GH_TOKEN": bool(os.environ.get("GH_TOKEN")),
        "GITHUB_TOKEN": bool(os.environ.get("GITHUB_TOKEN")),
    }
    return report


def provider_status(provider: str) -> dict[str, Any]:
    normalized = provider.strip().lower()
    if normalized == "github-copilot":
        return copilot_status("auto")
    if normalized == "openai":
        return {"success": True, "provider": "openai", "instructions": ["Use Codex/OpenAI's native browser or device login."], "raw_token_stored": False}
    if normalized == "google":
        return {"success": True, "provider": "google", "instructions": ["Use Gemini/Google's native browser, gcloud, or IDE login."], "raw_token_stored": False}
    if normalized == "ollama":
        return {
            "success": False,
            "provider": "ollama",
            "instructions": ["Ollama Cloud is not an official school provider; use Codex/OpenAI or Antigravity/Gemini."],
            "raw_token_stored": False,
            "official_school_route": False,
        }
    raise ValueError(f"unsupported auth provider: {provider}")
