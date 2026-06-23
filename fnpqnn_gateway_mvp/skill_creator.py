"""Skill entry/exit contracts for companion skill creation.

The gateway prepares handoff contracts. It does not install provider-specific
skills or expose secrets. A companion reads the entry path and writes the exit
path after producing or planning the skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from .bootstrap import BOOTSTRAP_PROFILES, build_bootstrap_plan, load_bootstrap_state


SKILL_ENTRY_DIR = ".fnpqnn_gateway/skill_entries"
SKILL_EXIT_DIR = ".fnpqnn_gateway/skill_exits"
ALLOWED_RESOURCES = ("scripts", "references", "assets")


@dataclass(frozen=True)
class SkillRoute:
    profile: str
    tool: str
    runtime_hook: str
    fingerprint: str
    workspace: str
    route_note: str

    def as_dict(self) -> dict[str, str]:
        return {
            "profile": self.profile,
            "tool": self.tool,
            "runtime_hook": self.runtime_hook,
            "fingerprint": self.fingerprint,
            "workspace": self.workspace,
            "route_note": self.route_note,
        }


PROFILE_NOTES = {
    "natural": "Create a local simulator skill contract without external provider coupling.",
    "codex": "Create a Codex-compatible skill plan with valid SKILL.md frontmatter.",
    "antigravity": "Create an Antigravity/Gemini handoff contract without installing Codex assets.",
    "vscode": "Create a Copilot/VS Code documentation and task handoff; Copilot stays support-only.",
    "ollama-cloud": "Create an Ollama/OpenClaw model-routing skill handoff.",
    "openclaw": "Create an OpenClaw control-plane skill handoff.",
    "cloud-kit": "Create a cloud bootstrap skill handoff with E2B/CloudKit boundaries.",
    "docker-kit": "Create a containerized bootstrap skill handoff.",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workspace_path(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve()


def normalize_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise ValueError("skill name must contain at least one letter or digit")
    if len(slug) >= 64:
        slug = slug[:63].rstrip("-")
    return slug


def _skill_paths(workspace: str | Path, skill_name: str) -> dict[str, str]:
    ws = _workspace_path(workspace)
    slug = normalize_skill_name(skill_name)
    return {
        "entry_json": str(ws / SKILL_ENTRY_DIR / f"{slug}.json"),
        "entry_markdown": str(ws / SKILL_ENTRY_DIR / f"{slug}.md"),
        "exit_json": str(ws / SKILL_EXIT_DIR / f"{slug}.json"),
        "exit_markdown": str(ws / SKILL_EXIT_DIR / f"{slug}.md"),
    }


def resolve_bootstrap_skill_route(
    *,
    workspace: str | Path = ".",
    profile: str | None = None,
    fingerprint: str | None = None,
    last: bool = False,
) -> dict[str, Any]:
    ws = _workspace_path(workspace)
    if last:
        state = load_bootstrap_state(ws)
        if not state.get("success"):
            return {
                "success": False,
                "error": "bootstrap state not found",
                "bootstrap_state": state,
                "next_step": "Run fnpqnn gateway bootstrap --profile <profile> --fingerprint <fp> --accept-fingerprint first, or pass --profile.",
            }
        selected_profile = str(state["profile"]["name"])
        route = SkillRoute(
            profile=selected_profile,
            tool=str(state["profile"]["tool"]),
            runtime_hook=str(state["runtime_hook"]),
            fingerprint=str(state["activation"]["fingerprint"]),
            workspace=str(ws),
            route_note=PROFILE_NOTES.get(selected_profile, "Create a skill handoff for the accepted bootstrap route."),
        )
        return {"success": True, "source": "last", "route": route.as_dict(), "bootstrap_state_path": state["paths"]["bootstrap"]}

    selected_profile = (profile or "natural").strip().lower()
    if selected_profile not in BOOTSTRAP_PROFILES:
        allowed = ", ".join(sorted(BOOTSTRAP_PROFILES))
        raise ValueError(f"unknown bootstrap profile '{profile}'. Allowed profiles: {allowed}")
    fp = fingerprint or f"profile-skill-{selected_profile}"
    plan = build_bootstrap_plan(selected_profile, fp, workspace=ws, accept_fingerprint=True)
    route = SkillRoute(
        profile=selected_profile,
        tool=str(plan["profile"]["tool"]),
        runtime_hook=str(plan["runtime_hook"]),
        fingerprint=fp,
        workspace=str(ws),
        route_note=PROFILE_NOTES.get(selected_profile, "Create a skill handoff for this bootstrap route."),
    )
    return {"success": True, "source": "profile", "route": route.as_dict(), "bootstrap_plan": plan}


def _skill_md_template(skill_name: str, goal: str) -> str:
    slug = normalize_skill_name(skill_name)
    return (
        "---\n"
        f"name: {slug}\n"
        f"description: {goal.strip()}\n"
        "---\n\n"
        f"# {slug}\n\n"
        "## Workflow\n\n"
        "1. Read the gateway skill entry contract.\n"
        "2. Respect the selected bootstrap fingerprint and provider boundary.\n"
        "3. Produce the requested skill artifacts without storing secrets.\n"
        "4. Write the exit contract with validation evidence.\n"
    )


def _entry_markdown(payload: dict[str, Any]) -> str:
    contract = payload["contract"]
    route = payload["bootstrap_route"]
    return (
        f"# Skill Entry: {contract['skill_name']}\n\n"
        f"- goal: {contract['goal']}\n"
        f"- profile: {route['profile']}\n"
        f"- tool: {route['tool']}\n"
        f"- runtime_hook: {route['runtime_hook']}\n"
        f"- fingerprint_ref: {contract['fingerprint_ref']}\n"
        f"- exit_path: {contract['exit_path']}\n\n"
        "## Required Outputs\n\n"
        + "\n".join(f"- {item}" for item in contract["required_outputs"])
        + "\n\n## Forbidden Actions\n\n"
        + "\n".join(f"- {item}" for item in contract["forbidden_actions"])
        + "\n"
    )


def _exit_markdown(payload: dict[str, Any]) -> str:
    return (
        f"# Skill Exit: {payload['skill_name']}\n\n"
        "- status: planned\n"
        "- validation_result: not-run\n\n"
        "The companion should replace this placeholder after creating or planning the skill.\n"
    )


def build_skill_entry(
    *,
    name: str,
    goal: str,
    workspace: str | Path = ".",
    profile: str | None = None,
    fingerprint: str | None = None,
    last: bool = False,
) -> dict[str, Any]:
    slug = normalize_skill_name(name)
    route_result = resolve_bootstrap_skill_route(workspace=workspace, profile=profile, fingerprint=fingerprint, last=last)
    if not route_result.get("success"):
        return route_result
    paths = _skill_paths(workspace, slug)
    route = route_result["route"]
    contract = {
        "skill_name": slug,
        "goal": goal,
        "bootstrap_profile": route["profile"],
        "fingerprint_ref": route["fingerprint"],
        "tool": route["tool"],
        "runtime_hook": route["runtime_hook"],
        "entry_path": paths["entry_json"],
        "entry_markdown_path": paths["entry_markdown"],
        "exit_path": paths["exit_json"],
        "exit_markdown_path": paths["exit_markdown"],
        "required_outputs": [
            "SKILL.md with name and description frontmatter",
            "minimal validation command",
            "handoff summary",
        ],
        "forbidden_actions": [
            "do not expose secrets",
            "do not overwrite existing skill unless --force",
            "do not install provider-specific assets without explicit write approval",
            "do not ask the user to paste tokens or edit dotenv files",
        ],
    }
    payload = {
        "success": True,
        "created_at": _now(),
        "skill_name": slug,
        "goal": goal,
        "workspace": str(_workspace_path(workspace)),
        "bootstrap_route": route,
        "route_source": route_result["source"],
        "contract": contract,
        "paths": paths,
        "raw_secret_stored": False,
        "dry_run": True,
    }
    payload["markdown_preview"] = _entry_markdown(payload)
    return payload


def build_skill_creator_plan(
    *,
    name: str,
    goal: str,
    workspace: str | Path = ".",
    profile: str | None = None,
    fingerprint: str | None = None,
    last: bool = False,
    output_path: str | Path | None = None,
    resources: list[str] | None = None,
    examples: bool = False,
) -> dict[str, Any]:
    entry = build_skill_entry(name=name, goal=goal, workspace=workspace, profile=profile, fingerprint=fingerprint, last=last)
    if not entry.get("success"):
        return entry
    slug = entry["skill_name"]
    ws = _workspace_path(workspace)
    base_output = Path(output_path).expanduser().resolve() if output_path else ws / ".fnpqnn_gateway" / "generated_skills"
    invalid = sorted(set(resources or []) - set(ALLOWED_RESOURCES))
    if invalid:
        raise ValueError(f"unknown skill resources: {', '.join(invalid)}")
    skill_dir = base_output / slug
    skill_md = skill_dir / "SKILL.md"
    validation_command = f"python C:\\Users\\jeans\\.codex\\skills\\.system\\skill-creator\\scripts\\quick_validate.py \"{skill_dir}\""
    exit_payload = {
        "status": "planned",
        "skill_name": slug,
        "created_skill_path": str(skill_dir),
        "artifacts": [str(skill_md), *(str(skill_dir / item) for item in (resources or []))],
        "validation_commands": [validation_command],
        "validation_result": "not-run",
        "handoff_summary": "Skill creation planned from gateway fingerprint route.",
    }
    payload = {
        **entry,
        "creator_plan": {
            "output_path": str(base_output),
            "skill_dir": str(skill_dir),
            "skill_md": str(skill_md),
            "skill_md_template": _skill_md_template(slug, goal),
            "resources": resources or [],
            "examples": examples,
            "validation_commands": [validation_command],
            "skill_creator_rules": {
                "name_kebab_case": True,
                "name_under_64_chars": len(slug) < 64,
                "skill_md_required": True,
                "frontmatter_required": ["name", "description"],
                "manual_install_requires_write": True,
            },
        },
        "exit_contract": exit_payload,
    }
    payload["markdown_preview"] = _entry_markdown(payload)
    payload["exit_markdown_preview"] = _exit_markdown(exit_payload)
    return payload


def _write_file(path: str | Path, content: str, *, force: bool, written: list[str], skipped: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        skipped.append(str(target))
        return
    target.write_text(content, encoding="utf-8")
    written.append(str(target))


def write_skill_entry(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not payload.get("success"):
        return payload
    written: list[str] = []
    skipped: list[str] = []
    entry_payload = {key: value for key, value in payload.items() if key not in {"markdown_preview", "exit_markdown_preview"}}
    paths = payload["paths"]
    _write_file(paths["entry_json"], json.dumps(entry_payload, indent=2, sort_keys=True), force=force, written=written, skipped=skipped)
    _write_file(paths["entry_markdown"], payload["markdown_preview"], force=force, written=written, skipped=skipped)
    exit_contract = payload.get("exit_contract", {
        "status": "planned",
        "skill_name": payload["skill_name"],
        "created_skill_path": "",
        "artifacts": [],
        "validation_commands": [],
        "validation_result": "not-run",
        "handoff_summary": "Awaiting companion skill output.",
    })
    _write_file(paths["exit_json"], json.dumps(exit_contract, indent=2, sort_keys=True), force=force, written=written, skipped=skipped)
    _write_file(paths["exit_markdown"], payload.get("exit_markdown_preview", _exit_markdown(exit_contract)), force=force, written=written, skipped=skipped)
    return {**payload, "dry_run": False, "written": written, "skipped_existing": skipped}


def write_skill_creator_plan(payload: dict[str, Any], *, force: bool = False, create_skill_files: bool = False) -> dict[str, Any]:
    result = write_skill_entry(payload, force=force)
    if not payload.get("success") or not create_skill_files:
        return result
    written = list(result.get("written", []))
    skipped = list(result.get("skipped_existing", []))
    plan = payload["creator_plan"]
    _write_file(plan["skill_md"], plan["skill_md_template"], force=force, written=written, skipped=skipped)
    for resource in plan["resources"]:
        Path(plan["skill_dir"], resource).mkdir(parents=True, exist_ok=True)
    return {**result, "written": written, "skipped_existing": skipped}
