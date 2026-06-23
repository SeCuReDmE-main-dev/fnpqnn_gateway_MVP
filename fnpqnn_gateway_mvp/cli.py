"""Command-line interface for FNP-QNN Gateway MVP."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import __version__
from .codeproject_client import status as codeproject_status
from .codeproject_mesh import mesh_status
from .hooks import DEFAULT_CODEPROJECT_URL, get_hook, list_hooks
from .natural_auth import copilot_status, provider_status
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

    auth = sub.add_parser("auth", help="Natural auth status for external developer tools.")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    natural = auth_sub.add_parser("natural-login", help="Show or inspect natural login state.")
    natural.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])
    natural.add_argument("--source", choices=["auto", "vscode", "copilot-cli", "gh"], default="auto")
    provider = auth_sub.add_parser("provider-status", help="Show one provider auth status.")
    provider.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])

    support = sub.add_parser("support", help="LLM-safe support diagnostics.")
    support_sub = support.add_subparsers(dest="support_command", required=True)
    support_provider_parser = support_sub.add_parser("provider", help="Show provider support report.")
    support_provider_parser.add_argument("provider", choices=["openai", "google", "ollama", "github-copilot"])
    support_sub.add_parser("all", help="Show all provider support reports.")
    return parser


def run_args(args: argparse.Namespace) -> int:
    as_json = bool(args.json)
    if args.section == "gateway":
        if args.gateway_command == "hooks":
            return _print({"success": True, "hooks": list_hooks()}, as_json)
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
    if args.section == "auth":
        if args.auth_command == "natural-login" and args.provider == "github-copilot":
            return _print(copilot_status(args.source), as_json)
        if args.auth_command == "natural-login":
            return _print(provider_status(args.provider), as_json)
        if args.auth_command == "provider-status":
            return _print(provider_status(args.provider), as_json)
    if args.section == "support":
        if args.support_command == "provider":
            return _print(support_provider(args.provider), as_json)
        if args.support_command == "all":
            return _print(support_all(), as_json)
    raise ValueError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_args(parser.parse_args(argv))
