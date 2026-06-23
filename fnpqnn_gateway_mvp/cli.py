"""Command-line interface for FNP-QNN Gateway MVP."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .activation import activate, list_activation_routes
from .bootstrap import bootstrap as bootstrap_profile
from .bootstrap import bootstrap_dry_run_plan, build_bootstrap_plan, list_bootstrap_profiles, start_bootstrap
from .capability_bridge import capability_map, skill_request
from .cloud_kit import e2b_ingest_plan, e2b_smoke, e2b_status
from .codeproject_client import status as codeproject_status, yolo_probe, yolo_training_probe
from .codeproject_mesh import mesh_status
from .deepsearch_skill import build_deepsearch_skill, write_deepsearch_skill
from .hooks import DEFAULT_CODEPROJECT_URL, get_hook, list_hooks
from .model_provider import list_model_provider_routes, model_provider_switch
from .natural_auth import copilot_status, provider_status
from .neutrosophic_gate import p114_consensus
from .obsidian_bridge import init_obsidian, lvfm_stream, obsidian_plan, query_notes, record_note
from .runner import run_bootstrap_plan, run_hook
from .skill_creator import build_skill_creator_plan, build_skill_entry, write_skill_creator_plan, write_skill_entry
from .support import support_all, support_provider
from .tunnel import tunnel_status
from .web_auth_login import auth_login, list_auth_login_systems


def _launch_simulator_tui() -> int:
    candidates = [
        [sys.executable, "-m", "fnp_qnn_cli.tui"],
        ["fnp-qnn-tui"],
        ["fnp-qnn", "tui"],
    ]
    for command in candidates:
        try:
            return subprocess.run(command, check=False).returncode
        except FileNotFoundError:
            continue
    print(
        json.dumps(
            {
                "success": False,
                "error": "FNP-QNN simulator TUI is not installed on this Python path.",
                "install_hint": "Install the simulator repo with pip install -e ../FNP-QNN-MVP, then run fnpqnn --tui.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1


def _print(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("success", True) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fnpqnn", description="Gateway CLI for FNP-QNN and CodeProject.AI backends.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output for structured commands.")
    parser.add_argument("--tui", action="store_true", help="Launch the branded FNP-QNN simulator TUI when available.")
    sub = parser.add_subparsers(dest="section")

    gateway = sub.add_parser("gateway", help="Run or inspect runtime gateway hooks.")
    gateway_sub = gateway.add_subparsers(dest="gateway_command", required=True)
    gateway_sub.add_parser("hooks", help="List runtime hooks.")
    gateway_sub.add_parser("activation-routes", help="List fingerprint-to-gateway activation routes.")
    gateway_sub.add_parser("bootstrap-profiles", help="List persistent bootstrap profiles.")
    gateway_bootstrap = gateway_sub.add_parser("bootstrap", help="Accept a fingerprint and persist a reusable bootstrap profile.")
    gateway_bootstrap.add_argument("--profile", required=True, choices=[item["name"] for item in list_bootstrap_profiles()])
    gateway_bootstrap.add_argument("--fingerprint")
    gateway_bootstrap.add_argument("--accept-fingerprint", action="store_true")
    gateway_bootstrap.add_argument("--workspace", default=".")
    gateway_bootstrap.add_argument("--port", type=int, default=8000)
    gateway_bootstrap.add_argument("--panel-port", type=int, default=5006)
    gateway_bootstrap.add_argument("--codeproject-url", default=DEFAULT_CODEPROJECT_URL)
    gateway_bootstrap.add_argument("--known-server", action="append", default=[])
    gateway_bootstrap.add_argument("--env-file", default=None)
    gateway_bootstrap.add_argument("--dry-run", action="store_true")
    gateway_bootstrap.add_argument("--force", action="store_true")
    gateway_start = gateway_sub.add_parser("start", help="Start the last accepted bootstrap profile.")
    gateway_start.add_argument("--workspace", default=".")
    gateway_start.add_argument("--profile", choices=[item["name"] for item in list_bootstrap_profiles()])
    gateway_start.add_argument("--port", type=int, default=None)
    gateway_start.add_argument("--codeproject-url", default=None)
    gateway_start.add_argument("--known-server", action="append", default=[])
    gateway_start.add_argument("--jsonl", action="store_true")
    gateway_start.add_argument("--dry-run", action="store_true")
    gateway_start.add_argument("--no-preflight", action="store_true")
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
    gateway_skill_entry = gateway_sub.add_parser("skill-entry", help="Create a skill entry/exit contract for a companion.")
    gateway_skill_entry.add_argument("--name", required=True)
    gateway_skill_entry.add_argument("--goal", required=True)
    gateway_skill_entry.add_argument("--workspace", default=".")
    gateway_skill_entry.add_argument("--profile", choices=[item["name"] for item in list_bootstrap_profiles()])
    gateway_skill_entry.add_argument("--fingerprint")
    gateway_skill_entry.add_argument("--last", action="store_true")
    gateway_skill_entry.add_argument("--dry-run", action="store_true")
    gateway_skill_entry.add_argument("--write", action="store_true")
    gateway_skill_entry.add_argument("--force", action="store_true")
    gateway_skill_create = gateway_sub.add_parser("skill-create", help="Create a complete skill creator handoff plan.")
    gateway_skill_create.add_argument("--name", required=True)
    gateway_skill_create.add_argument("--goal", required=True)
    gateway_skill_create.add_argument("--workspace", default=".")
    gateway_skill_create.add_argument("--profile", choices=[item["name"] for item in list_bootstrap_profiles()])
    gateway_skill_create.add_argument("--fingerprint")
    gateway_skill_create.add_argument("--last", action="store_true")
    gateway_skill_create.add_argument("--output-path")
    gateway_skill_create.add_argument("--resources", default="")
    gateway_skill_create.add_argument("--examples", action="store_true")
    gateway_skill_create.add_argument("--create-files", action="store_true")
    gateway_skill_create.add_argument("--dry-run", action="store_true")
    gateway_skill_create.add_argument("--write", action="store_true")
    gateway_skill_create.add_argument("--force", action="store_true")
    gateway_deepsearch = gateway_sub.add_parser("deepsearch-skill", help="Create a provider-native simulator web-search/deepsearch contract.")
    gateway_deepsearch.add_argument("--query", required=True)
    gateway_deepsearch.add_argument("--research-goal")
    gateway_deepsearch.add_argument("--workspace", default=".")
    gateway_deepsearch.add_argument("--system")
    gateway_deepsearch.add_argument("--last-auth", action="store_true")
    gateway_deepsearch.add_argument("--fingerprint")
    gateway_deepsearch.add_argument("--dry-run", action="store_true")
    gateway_deepsearch.add_argument("--write", action="store_true")
    gateway_deepsearch.add_argument("--force", action="store_true")
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
    gateway_run.add_argument("--hook")
    gateway_run.add_argument("--profile", choices=[item["name"] for item in list_bootstrap_profiles()])
    gateway_run.add_argument("--last", action="store_true", help="Run the last accepted bootstrap profile.")
    gateway_run.add_argument("--workspace", default=".")
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
    auth_sub.add_parser("systems", help="List web-auth login systems.")
    auth_login_parser = auth_sub.add_parser("login", help="Build a web-auth login handoff for one gateway system.")
    auth_login_parser.add_argument("--system", required=True)
    auth_login_parser.add_argument("--fingerprint")
    auth_login_parser.add_argument("--accept-fingerprint", action="store_true")
    auth_login_parser.add_argument("--workspace", default=".")
    auth_login_parser.add_argument("--open-browser", action="store_true")
    auth_login_parser.add_argument("--dry-run", action="store_true")
    auth_login_parser.add_argument("--write", action="store_true")
    auth_login_parser.add_argument("--force", action="store_true")
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
    auth_sub.add_parser("provider-routes", help="List model provider/auth source routes.")
    model_switch = auth_sub.add_parser("model-switch", help="Switch model provider/auth source from a fingerprint route.")
    model_switch.add_argument("--tool")
    model_switch.add_argument("--fingerprint")
    model_switch.add_argument("--last", action="store_true", help="Resolve tool and fingerprint from the last gateway bootstrap.")
    model_switch.add_argument("--workspace", default=".")
    model_switch.add_argument("--source", choices=["auto", "web-auth", "native-login", "petit-yolo-instructions"], default="auto")
    model_switch.add_argument("--dry-run", action="store_true")
    model_switch.add_argument("--write", action="store_true")
    model_switch.add_argument("--force", action="store_true")

    function = sub.add_parser("function", help="Function-style gateway operations for companion CLIs.")
    function_sub = function.add_subparsers(dest="function_command", required=True)
    provider_switch = function_sub.add_parser("provider-switch", help="Alias for auth model-switch.")
    provider_switch.add_argument("--tool")
    provider_switch.add_argument("--fingerprint")
    provider_switch.add_argument("--last", action="store_true")
    provider_switch.add_argument("--workspace", default=".")
    provider_switch.add_argument("--source", choices=["auto", "web-auth", "native-login", "petit-yolo-instructions"], default="auto")
    provider_switch.add_argument("--dry-run", action="store_true")
    provider_switch.add_argument("--write", action="store_true")
    provider_switch.add_argument("--force", action="store_true")
    function_auth_login = function_sub.add_parser("auth-login", help="Alias for auth login.")
    function_auth_login.add_argument("--system", required=True)
    function_auth_login.add_argument("--fingerprint")
    function_auth_login.add_argument("--accept-fingerprint", action="store_true")
    function_auth_login.add_argument("--workspace", default=".")
    function_auth_login.add_argument("--open-browser", action="store_true")
    function_auth_login.add_argument("--dry-run", action="store_true")
    function_auth_login.add_argument("--write", action="store_true")
    function_auth_login.add_argument("--force", action="store_true")
    function_skill_creator = function_sub.add_parser("skill-creator", help="Alias for gateway skill-create.")
    function_skill_creator.add_argument("--name", required=True)
    function_skill_creator.add_argument("--goal", required=True)
    function_skill_creator.add_argument("--workspace", default=".")
    function_skill_creator.add_argument("--profile", choices=[item["name"] for item in list_bootstrap_profiles()])
    function_skill_creator.add_argument("--fingerprint")
    function_skill_creator.add_argument("--last", action="store_true")
    function_skill_creator.add_argument("--output-path")
    function_skill_creator.add_argument("--resources", default="")
    function_skill_creator.add_argument("--examples", action="store_true")
    function_skill_creator.add_argument("--create-files", action="store_true")
    function_skill_creator.add_argument("--dry-run", action="store_true")
    function_skill_creator.add_argument("--write", action="store_true")
    function_skill_creator.add_argument("--force", action="store_true")
    function_deepsearch = function_sub.add_parser("deepsearch", help="Alias for gateway deepsearch-skill.")
    function_deepsearch.add_argument("--query", required=True)
    function_deepsearch.add_argument("--research-goal")
    function_deepsearch.add_argument("--workspace", default=".")
    function_deepsearch.add_argument("--system")
    function_deepsearch.add_argument("--last-auth", action="store_true")
    function_deepsearch.add_argument("--fingerprint")
    function_deepsearch.add_argument("--dry-run", action="store_true")
    function_deepsearch.add_argument("--write", action="store_true")
    function_deepsearch.add_argument("--force", action="store_true")

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
    obsidian_record.add_argument("--neutrosophic-gate", choices=["p114", "none"], default="p114")
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
    p114 = memory_sub.add_parser("p114-consensus", help="Run p114 neutrosophic consensus for gateway admission items.")
    p114.add_argument("--item", action="append", default=[])
    p114.add_argument("--mode", choices=["consensus", "decision", "score_evidence", "case_study_audit"], default="score_evidence")

    cloud = sub.add_parser("cloud", help="Optional cloud kit bridges for external data ingestion.")
    cloud_sub = cloud.add_subparsers(dest="cloud_command", required=True)
    cloud_sub.add_parser("e2b-status", help="Inspect E2B cloud kit readiness without printing secrets.")
    e2b_smoke_parser = cloud_sub.add_parser("e2b-smoke", help="Run a real minimal E2B sandbox smoke test.")
    e2b_smoke_parser.add_argument("--env-file", default=str(Path.home() / ".openclaw" / "workspace" / ".env"))
    e2b_plan = cloud_sub.add_parser("e2b-ingest-plan", help="Plan external data ingestion through E2B into Obsidian and LVFM.")
    e2b_plan.add_argument("--tool", required=True)
    e2b_plan.add_argument("--source", required=True)
    e2b_plan.add_argument("--title", required=True)
    e2b_plan.add_argument("--workspace", default=".")
    e2b_plan.add_argument("--vault")
    e2b_plan.add_argument("--dry-run", action="store_true")
    e2b_plan.add_argument("--write", action="store_true")
    e2b_plan.add_argument("--force", action="store_true")
    return parser


def run_args(args: argparse.Namespace) -> int:
    as_json = bool(args.json)
    if getattr(args, "tui", False):
        return _launch_simulator_tui()
    if not args.section:
        raise ValueError("a command is required unless --tui is used")
    if args.section == "gateway":
        if args.gateway_command == "hooks":
            return _print({"success": True, "hooks": list_hooks()}, as_json)
        if args.gateway_command == "activation-routes":
            return _print({"success": True, "routes": list_activation_routes()}, as_json)
        if args.gateway_command == "bootstrap-profiles":
            return _print({"success": True, "profiles": list_bootstrap_profiles()}, as_json)
        if args.gateway_command == "bootstrap":
            fingerprint = args.fingerprint or f"dry-run-{args.profile}"
            if not args.fingerprint and not args.dry_run:
                raise ValueError("gateway bootstrap requires --fingerprint unless --dry-run is used")
            payload = bootstrap_profile(
                args.profile,
                fingerprint,
                workspace=args.workspace,
                accept_fingerprint=args.accept_fingerprint or args.dry_run,
                port=args.port,
                panel_port=args.panel_port,
                codeproject_url=args.codeproject_url,
                known_servers=args.known_server,
                env_file=args.env_file,
                dry_run=args.dry_run,
                force=args.force,
            )
            return _print(payload, as_json)
        if args.gateway_command == "start":
            return start_bootstrap(
                workspace=args.workspace,
                profile=args.profile,
                port=args.port,
                codeproject_url=args.codeproject_url,
                known_servers=args.known_server,
                jsonl=args.jsonl,
                dry_run=args.dry_run,
                no_preflight=args.no_preflight,
            )
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
        if args.gateway_command == "skill-entry":
            payload = build_skill_entry(
                name=args.name,
                goal=args.goal,
                workspace=args.workspace,
                profile=args.profile,
                fingerprint=args.fingerprint,
                last=args.last,
            )
            if args.write and not args.dry_run:
                payload = write_skill_entry(payload, force=args.force)
            return _print(payload, as_json)
        if args.gateway_command == "skill-create":
            resources = [item.strip() for item in args.resources.split(",") if item.strip()]
            payload = build_skill_creator_plan(
                name=args.name,
                goal=args.goal,
                workspace=args.workspace,
                profile=args.profile,
                fingerprint=args.fingerprint,
                last=args.last,
                output_path=args.output_path,
                resources=resources,
                examples=args.examples,
            )
            if args.write and not args.dry_run:
                payload = write_skill_creator_plan(payload, force=args.force, create_skill_files=args.create_files)
            return _print(payload, as_json)
        if args.gateway_command == "deepsearch-skill":
            payload = build_deepsearch_skill(
                query=args.query,
                research_goal=args.research_goal,
                workspace=args.workspace,
                system=args.system,
                last_auth=args.last_auth,
                fingerprint=args.fingerprint,
            )
            if args.write and not args.dry_run:
                payload = write_deepsearch_skill(payload, force=args.force)
            return _print(payload, as_json)
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
            if args.last:
                return start_bootstrap(
                    workspace=args.workspace,
                    port=args.port,
                    codeproject_url=args.codeproject_url,
                    known_servers=args.known_server,
                    jsonl=args.jsonl,
                    dry_run=args.dry_run,
                    no_preflight=args.no_preflight,
                )
            if args.profile:
                plan = build_bootstrap_plan(
                    args.profile,
                    f"profile-run-{args.profile}",
                    workspace=args.workspace,
                    accept_fingerprint=True,
                    port=args.port,
                    codeproject_url=args.codeproject_url,
                    known_servers=args.known_server,
                )
                if args.dry_run:
                    return _print(bootstrap_dry_run_plan(plan), as_json)
                return run_bootstrap_plan(plan, jsonl=args.jsonl, no_preflight=args.no_preflight)
            if not args.hook:
                raise ValueError("gateway run requires --hook, --profile, or --last")
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
        if args.auth_command == "systems":
            return _print({"success": True, "systems": list_auth_login_systems()}, as_json)
        if args.auth_command == "login":
            return _print(
                auth_login(
                    args.system,
                    workspace=args.workspace,
                    fingerprint=args.fingerprint,
                    accept_fingerprint=args.accept_fingerprint,
                    open_browser=args.open_browser,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
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
        if args.auth_command == "provider-routes":
            return _print({"success": True, "routes": list_model_provider_routes()}, as_json)
        if args.auth_command == "model-switch":
            return _print(
                model_provider_switch(
                    tool=args.tool,
                    fingerprint=args.fingerprint,
                    workspace=args.workspace,
                    last=args.last,
                    source=args.source,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
    if args.section == "function":
        if args.function_command == "provider-switch":
            return _print(
                model_provider_switch(
                    tool=args.tool,
                    fingerprint=args.fingerprint,
                    workspace=args.workspace,
                    last=args.last,
                    source=args.source,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
        if args.function_command == "auth-login":
            return _print(
                auth_login(
                    args.system,
                    workspace=args.workspace,
                    fingerprint=args.fingerprint,
                    accept_fingerprint=args.accept_fingerprint,
                    open_browser=args.open_browser,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
        if args.function_command == "skill-creator":
            resources = [item.strip() for item in args.resources.split(",") if item.strip()]
            payload = build_skill_creator_plan(
                name=args.name,
                goal=args.goal,
                workspace=args.workspace,
                profile=args.profile,
                fingerprint=args.fingerprint,
                last=args.last,
                output_path=args.output_path,
                resources=resources,
                examples=args.examples,
            )
            if args.write and not args.dry_run:
                payload = write_skill_creator_plan(payload, force=args.force, create_skill_files=args.create_files)
            return _print(payload, as_json)
        if args.function_command == "deepsearch":
            payload = build_deepsearch_skill(
                query=args.query,
                research_goal=args.research_goal,
                workspace=args.workspace,
                system=args.system,
                last_auth=args.last_auth,
                fingerprint=args.fingerprint,
            )
            if args.write and not args.dry_run:
                payload = write_deepsearch_skill(payload, force=args.force)
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
                    neutrosophic_gate=args.neutrosophic_gate,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
        if args.memory_command == "obsidian-query":
            return _print(query_notes(args.query, args.workspace, args.vault, args.limit), as_json)
        if args.memory_command == "obsidian-lvfm-stream":
            return _print(lvfm_stream(args.query, args.workspace, args.vault, args.limit), as_json)
        if args.memory_command == "p114-consensus":
            return _print(p114_consensus(args.item, mode=args.mode), as_json)
    if args.section == "cloud":
        if args.cloud_command == "e2b-status":
            return _print(e2b_status(), as_json)
        if args.cloud_command == "e2b-smoke":
            return _print(e2b_smoke(args.env_file), as_json)
        if args.cloud_command == "e2b-ingest-plan":
            return _print(
                e2b_ingest_plan(
                    args.tool,
                    args.source,
                    args.title,
                    workspace=args.workspace,
                    vault=args.vault,
                    write=args.write and not args.dry_run,
                    force=args.force,
                ),
                as_json,
            )
    raise ValueError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_args(parser.parse_args(argv))
