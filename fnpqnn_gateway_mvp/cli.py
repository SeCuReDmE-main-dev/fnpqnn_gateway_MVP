"""Command-line interface for FNP-QNN Gateway MVP."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import __version__
from .activation import activate, list_activation_routes
from .capability_bridge import capability_map, skill_request
from .codeproject_client import status as codeproject_status, yolo_probe, yolo_training_probe
from .codeproject_mesh import mesh_status
from .hooks import DEFAULT_CODEPROJECT_URL, get_hook, list_hooks
from .natural_auth import copilot_status, provider_status
from .obsidian_bridge import init_obsidian, lvfm_stream, obsidian_plan, query_notes, record_note
from .runner import run_hook
from .support import support_all, support_provider
from .tunnel import tunnel_status


def _print(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("success", True) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fnpqnn", description="Gateway CLI for FNP-QNN and CodeProject.AI backends.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output for structured commands.")
    sub = parser.add_subparsers(dest="section", required=True)

    gateway = sub.add_parser("gateway", help="Run or inspect runtime gateway hooks.")
    gateway_sub = gateway.add_subparsers(dest="gateway_command", required=True)
    gateway_sub.add_parser("hooks", help="List runtime hooks.")
    gateway_sub.add_parser("activation-routes", help="List fingerprint-to-gateway activation routes.")
    gateway_capability = gateway_sub.add_parser("capability-map", help="Show the native-tool/simulator capability split.")
    gateway_capability.add_argument("--tool", required=True)
    gateway_capability.add_argument("--workspace", default=".")
    gateway_skill = gateway_sub.add_parser("skill-request", help="Create a native tool request for a simulator skill/gate.")
    gateway_skill.add_argument("--tool", required=True)
    gateway_skill.add_argument("--name", required=True)
    gateway_skill.add_argument("--goal", required=True)
    gateway_skill.add_argument("--workspace", default=".")
    gateway_skill.add_argument("--dry-run", action="store_true")
    gateway_skill.add_argument("--write", action="store_true")
    gateway_skill.add_argument("--force", action="store_true")
    gateway_activate = gateway_sub.add_parser("activate", help="Accept a fingerprint and activate the matching gateway route.")
    gateway_activate.add_argument("--tool", required=True)
    gateway_activate.add_argument("--fingerprint", required=True)
    gateway_activate.add_argument("--accept-fingerprint", action="store_true")
    gateway_activate.add_argument("--workspace", default=".")
    gateway_activate.add_argument("--codeproject-url", default=DEFAULT_CODEPROJECT_URL)
    gateway_activate.add_argument("--known-server", action="append", default=[])
    gateway_activate.add_argument("--dry-run", action="store_true")
    gateway_activate.add_argument("--write", action="store_true")
    gateway_activate.add_argument("--force", action="store_true")
    gateway_run = gateway_sub.add_parser("run", help="Run a gateway hook and stream logs.")
    gateway_run.add_argument("--hook", required=True)
    gateway_run.add_argument("--host", default="127.0.0.1")
    gateway_run.add_argument("--port", type=int, default=8000)
    gateway_run.add_argument("--codeproject-url", default=DEFAULT_CODEPROJECT_URL)
    gateway_run.add_argument("--known-server", action="append", default=[])
    gateway_run.add_argument("--mesh", action="store_true", help="Use mesh diagnostics for CodeProject.AI hooks.")
    gateway_run.add_argument("--jsonl", action="store_true")
    gateway_run.add_argument("--dry-run", action="store_true")
    gateway_run.add_argument("--no-preflight", action="store_true")
    gateway_doctor = gateway_sub.add_parser("doctor", help="Diagnose one hook without starting a long-running server.")
    gateway_doctor.add_argument("--hook", required=True)
    gateway_doctor.add_argument("--codeproject-url", default=DEFAULT_CODEPROJECT_URL)
    gateway_doctor.add_argument("--known-server", action="append", default=[])
    gateway_doctor.add_argument("--mesh", action="store_true", help="Use mesh diagnostics for CodeProject.AI hooks.")
    gateway_sub.add_parser("version", help="Show gateway version.")

    codeproject = sub.add_parser("codeproject", help="Inspect CodeProject.AI Server endpoints, mesh, and tunnels.")
    cp_sub = codeproject.add_subparsers(dest="codeproject_command", required=True)
    cp_status = cp_sub.add_parser("status", help="Check a CodeProject.AI Server URL.")
    cp_status.add_argument("--url", default=DEFAULT_CODEPROJECT_URL)
    cp_status.add_argument("--dry-run", action="store_true")
    cp_mesh = cp_sub.add_parser("mesh-status", help="Check CodeProject.AI mesh readiness.")
    cp_mesh.add_argument("--url", default=DEFAULT_CODEPROJECT_URL)
    cp_mesh.add_argument("--known-server", action="append", default=[])
    cp_mesh.add_argument("--dry-run", action="store_true")
    cp_tunnel = cp_sub.add_parser("tunnel", help="Validate a VS Code/IDE forwarded CodeProject.AI URL.")
    cp_tunnel.add_argument("--url", "--tunnel-url", dest="url", required=True)
    cp_tunnel.add_argument("--dry-run", action="store_true")
    cp_yolo = cp_sub.add_parser("yolo-status", help="Check CodeProject.AI YOLO/instruct backend readiness.")
    cp_yolo.add_argument("--url", default=DEFAULT_CODEPROJECT_URL)
    cp_yolo.add_argument("--image")
    cp_yolo.add_argument("--min-confidence", type=float, default=0.4)
    cp_yolo.add_argument("--dry-run", action="store_true")
    cp_yolo_train = cp_sub.add_parser("yolo-training-status", help="Check the explicit CodeProject.AI Training for YoloV5 6.2 module routes.")
    cp_yolo_train.add_argument("--url", default=DEFAULT_CODEPROJECT_URL)
    cp_yolo_train.add_argument("--model-name")
    cp_yolo_train.add_argument("--dataset-name")
    cp_yolo_train.add_argument("--dry-run", action="store_true")

    auth = sub.add_parser("auth", help="Natural auth status for external developer tools.")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    natural = auth_sub.add_parser("natural-login", help="Show or inspect natural login state.")
    natural.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])
    natural.add_argument("--source", choices=["auto", "vscode", "copilot-cli", "gh"], default="auto")
    provider = auth_sub.add_parser("provider-status", help="Show one provider auth status.")
    provider.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])
    fingerprint = auth_sub.add_parser("fingerprint", help="Fingerprint approval and handoff commands.")
    fingerprint_sub = fingerprint.add_subparsers(dest="fingerprint_command", required=True)
    fingerprint_accept = fingerprint_sub.add_parser("accept", help="Accept a login fingerprint and build the gateway activation plan.")
    fingerprint_accept.add_argument("--tool", required=True)
    fingerprint_accept.add_argument("--fingerprint", required=True)
    fingerprint_accept.add_argument("--workspace", default=".")
    fingerprint_accept.add_argument("--codeproject-url", default=DEFAULT_CODEPROJECT_URL)
    fingerprint_accept.add_argument("--known-server", action="append", default=[])
    fingerprint_accept.add_argument("--dry-run", action="store_true")
    fingerprint_accept.add_argument("--write", action="store_true")
    fingerprint_accept.add_argument("--force", action="store_true")

    support = sub.add_parser("support", help="LLM-safe support diagnostics.")
    support_sub = support.add_subparsers(dest="support_command", required=True)
    support_provider_parser = support_sub.add_parser("provider", help="Show provider support report.")
    support_provider_parser.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])
    support_sub.add_parser("all", help="Show all provider support reports.")

    memory = sub.add_parser("memory", help="Persistent gateway memory and Obsidian RAG bridge.")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    obsidian_init = memory_sub.add_parser("obsidian-init", help="Plan or create an Obsidian-style gateway RAG vault.")
    obsidian_init.add_argument("--tool", required=True)
    obsidian_init.add_argument("--workspace", default=".")
    obsidian_init.add_argument("--vault")
    obsidian_init.add_argument("--dry-run", action="store_true")
    obsidian_init.add_argument("--write", action="store_true")
    obsidian_init.add_argument("--force", action="store_true")
    obsidian_record = memory_sub.add_parser("obsidian-record", help="Record an admitted native-tool or gateway memory note.")
    obsidian_record.add_argument("--tool", required=True)
    obsidian_record.add_argument("--title", required=True)
    obsidian_record.add_argument("--content", required=True)
    obsidian_record.add_argument("--workspace", default=".")
    obsidian_record.add_argument("--vault")
    obsidian_record.add_argument("--tag", action="append", default=[])
    obsidian_record.add_argument("--source", default="gateway-note")
    obsidian_record.add_argument("--dry-run", action="store_true")
    obsidian_record.add_argument("--write", action="store_true")
    obsidian_record.add_argument("--force", action="store_true")
    obsidian_query = memory_sub.add_parser("obsidian-query", help="Query admitted Obsidian gateway RAG notes.")
    obsidian_query.add_argument("--query", required=True)
    obsidian_query.add_argument("--workspace", default=".")
    obsidian_query.add_argument("--vault")
    obsidian_query.add_argument("--limit", type=int, default=5)
    obsidian_lvfm = memory_sub.add_parser("obsidian-lvfm-stream", help="Convert admitted Obsidian notes into a Cerebrum/LVFM candidate stream.")
    obsidian_lvfm.add_argument("--query", required=True)
    obsidian_lvfm.add_argument("--workspace", default=".")
    obsidian_lvfm.add_argument("--vault")
    obsidian_lvfm.add_argument("--limit", type=int, default=5)
    return parser


def run_args(args: argparse.Namespace) -> int:
    as_json = bool(args.json)
    if args.section == "gateway":
        if args.gateway_command == "hooks":
            return _print({"success": True, "hooks": list_hooks()}, as_json)
        if args.gateway_command == "activation-routes":
            return _print({"success": True, "routes": list_activation_routes()}, as_json)
        if args.gateway_command == "capability-map":
            return _print(capability_map(args.tool, workspace=args.workspace), as_json)
        if args.gateway_command == "skill-request":
            return _print(
                skill_request(
                    tool=args.tool,
                    name=args.name,
                    goal=args.goal,
                    workspace=args.workspace,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
        if args.gateway_command == "activate":
            payload = activate(
                tool=args.tool,
                fingerprint=args.fingerprint,
                workspace=args.workspace,
                accept_fingerprint=args.accept_fingerprint,
                codeproject_url=args.codeproject_url,
                known_servers=args.known_server,
                write=args.write and not args.dry_run,
                force=args.force,
            )
            return _print(payload, as_json)
        if args.gateway_command == "version":
            return _print({"success": True, "version": __version__}, as_json)
        if args.gateway_command == "doctor":
            hook = get_hook("codeproject-ai-mesh" if args.mesh and args.hook == "codeproject-ai" else args.hook)
            if hook.codeproject:
                payload = mesh_status(args.codeproject_url, known_servers=args.known_server, dry_run=True) if hook.mesh else codeproject_status(args.codeproject_url, dry_run=True)
            else:
                payload = {"success": True, "hook": hook.as_dict(), "dry_run": True}
            return _print(payload, as_json)
        if args.gateway_command == "run":
            hook = get_hook("codeproject-ai-mesh" if args.mesh and args.hook == "codeproject-ai" else args.hook)
            return run_hook(
                hook,
                port=args.port,
                host=args.host,
                codeproject_url=args.codeproject_url,
                known_servers=args.known_server,
                jsonl=args.jsonl,
                dry_run=args.dry_run,
                no_preflight=args.no_preflight,
            )
    if args.section == "codeproject":
        if args.codeproject_command == "status":
            return _print(codeproject_status(args.url, dry_run=args.dry_run), as_json)
        if args.codeproject_command == "mesh-status":
            return _print(mesh_status(args.url, known_servers=args.known_server, dry_run=args.dry_run), as_json)
        if args.codeproject_command == "tunnel":
            return _print(tunnel_status(args.url, dry_run=args.dry_run), as_json)
        if args.codeproject_command == "yolo-status":
            return _print(yolo_probe(args.url, dry_run=args.dry_run, image_path=args.image, min_confidence=args.min_confidence), as_json)
        if args.codeproject_command == "yolo-training-status":
            return _print(
                yolo_training_probe(
                    args.url,
                    dry_run=args.dry_run,
                    model_name=args.model_name,
                    dataset_name=args.dataset_name,
                ),
                as_json,
            )
    if args.section == "auth":
        if args.auth_command == "natural-login" and args.provider == "github-copilot":
            return _print(copilot_status(args.source), as_json)
        if args.auth_command == "natural-login":
            return _print(provider_status(args.provider), as_json)
        if args.auth_command == "provider-status":
            return _print(provider_status(args.provider), as_json)
        if args.auth_command == "fingerprint" and args.fingerprint_command == "accept":
            payload = activate(
                tool=args.tool,
                fingerprint=args.fingerprint,
                workspace=args.workspace,
                accept_fingerprint=True,
                codeproject_url=args.codeproject_url,
                known_servers=args.known_server,
                write=args.write and not args.dry_run,
                force=args.force,
            )
            return _print(payload, as_json)
    if args.section == "support":
        if args.support_command == "provider":
            return _print(support_provider(args.provider), as_json)
        if args.support_command == "all":
            return _print(support_all(), as_json)
    if args.section == "memory":
        if args.memory_command == "obsidian-init":
            if args.write and not args.dry_run:
                return _print(init_obsidian(args.tool, args.workspace, args.vault, write=True, force=args.force), as_json)
            return _print(obsidian_plan(args.tool, args.workspace, args.vault), as_json)
        if args.memory_command == "obsidian-record":
            return _print(
                record_note(
                    args.tool,
                    args.title,
                    args.content,
                    workspace=args.workspace,
                    vault=args.vault,
                    tags=args.tag,
                    source=args.source,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
        if args.memory_command == "obsidian-query":
            return _print(query_notes(args.query, args.workspace, args.vault, args.limit), as_json)
        if args.memory_command == "obsidian-lvfm-stream":
            return _print(lvfm_stream(args.query, args.workspace, args.vault, args.limit), as_json)
    raise ValueError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_args(parser.parse_args(argv))
