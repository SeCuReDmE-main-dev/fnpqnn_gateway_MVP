from __future__ import annotations

import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
import threading
import unittest

from fnpqnn_gateway_mvp.cli import main
from fnpqnn_gateway_mvp.activation import activate, activation_plan, route_for_tool
from fnpqnn_gateway_mvp.bootstrap import bootstrap, build_bootstrap_plan, load_bootstrap_state
from fnpqnn_gateway_mvp.capability_bridge import capability_map, skill_request
from fnpqnn_gateway_mvp.cloud_kit import e2b_ingest_plan, e2b_smoke, e2b_status
from fnpqnn_gateway_mvp.codeproject_client import DEFAULT_PROBE_ROUTES, YOLO_TRAINING_MODULE, status, yolo_probe, yolo_training_probe
from fnpqnn_gateway_mvp.codeproject_mesh import DOCKER_TCP_MAPPING, DOCKER_UDP_MAPPING, mesh_status
from fnpqnn_gateway_mvp.deepsearch_skill import build_deepsearch_skill, write_deepsearch_skill
from fnpqnn_gateway_mvp.hooks import HOOKS
from fnpqnn_gateway_mvp.model_provider import build_model_provider_switch, model_provider_switch
from fnpqnn_gateway_mvp.neutrosophic_gate import p114_consensus
from fnpqnn_gateway_mvp.obsidian_bridge import init_obsidian, lvfm_stream, query_notes, record_note
from fnpqnn_gateway_mvp.qlc_env import load_openclaw_tool_env, qlc_tool_readiness
from fnpqnn_gateway_mvp.qlc_submit import build_gateway_loop_receipt, extract_gateway_submission, qlc_submit
from fnpqnn_gateway_mvp.skill_creator import build_skill_creator_plan, build_skill_entry, write_skill_creator_plan, write_skill_entry
from fnpqnn_gateway_mvp.support import support_all
from fnpqnn_gateway_mvp.telemetry import _sanitize as sanitize_metric_token
from fnpqnn_gateway_mvp.tunnel import tunnel_status
from fnpqnn_gateway_mvp.web_auth_login import auth_login, list_auth_login_systems


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "qlc_contract"


def _qlc_workflow_bundle() -> dict:
    mesh_payload = {
        "memories": [
            {
                "modality": "stimuli",
                "starting_time": 0.0,
                "ending_time": 1.0,
                "value": 0.7,
                "label": "qlc-container",
                "source": "ffed-qlc-mvp",
                "payload_ref": "asset-001",
            }
        ],
        "label": 1.0,
        "epochs": 2,
        "run_qnn": True,
        "plugin_hook_enabled": True,
        "plugin_set": "mvp5",
        "plugin_context": {
            "orchestrator": "CeLeBrUm",
            "runtime_memory_surface": "Cerebrum",
            "sensitivity_weighted_obfuscation_policy": {
                "schema": "ffed.qlc.sensitivity_weighted_obfuscation_policy.v1",
                "media_type": "image",
                "sensitivity_level": "high",
            },
        },
        "cpai_context": {"mesh_enabled": True, "can_connect": True},
    }
    return {
        "schema": "ffed.qlc.protection_workflow_bundle.v1",
        "contract_version": "qlc-wiring-contract.v2",
        "source_id": "asset-001",
        "media_type": "image",
        "workflow_fingerprint": "wf-fp",
        "artifacts": {},
        "gateway_submission": {
            "schema": "ffed.qlc.gateway_submission.v1",
            "contract_version": "qlc-wiring-contract.v2",
            "source_workflow_schema": "ffed.qlc.protection_workflow_bundle.v1",
            "workflow_fingerprint": "wf-fp",
            "target_endpoint": "POST /cerebrum/runtime/run",
            "route_action": "submit_to_cerebrum",
            "mesh_payload": mesh_payload,
            "mesh_payload_fingerprint": "mesh-fp",
            "raw_payload_embedded": False,
        },
        "raw_payload_embedded": False,
    }


class GatewayCliTests(unittest.TestCase):
    def capture(self, argv: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, stream.getvalue()

    def test_runtime_hooks_include_codeproject(self) -> None:
        expected = {
            "simulator",
            "codex",
            "gemini",
            "antigravity",
            "ollama",
            "ollama-cloud",
            "agent-platform",
            "openclaw",
            "codeproject-ai",
            "codeproject-ai-server",
            "codeproject-ai-mesh",
        }
        self.assertTrue(expected.issubset(set(HOOKS)))

    def test_github_copilot_is_auth_provider_not_runtime_hook(self) -> None:
        self.assertNotIn("github-copilot", HOOKS)
        support = support_all()
        self.assertIn("github-copilot", support["providers"])
        self.assertFalse(support["providers"]["github-copilot"]["copilot_is_runtime_hook"])

    def test_codeproject_status_dry_run_builds_expected_probe(self) -> None:
        payload = status("http://localhost:32168", dry_run=True)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["url"], "http://localhost:32168")
        self.assertIn("/", payload["routes"])
        self.assertEqual(DEFAULT_PROBE_ROUTES[1], "/v1/vision/detect/scene")

    def test_tunnel_url_is_accepted_and_normalized(self) -> None:
        payload = tunnel_status("localhost:32168", dry_run=True)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["url"], "http://localhost:32168")
        self.assertEqual(payload["credential_storage"], "none")

    def test_mesh_doctor_reports_tcp_udp_expectations(self) -> None:
        payload = mesh_status("http://localhost:32168", known_servers=["ai-node-01"], dry_run=True)
        self.assertTrue(payload["success"])
        self.assertIn(DOCKER_TCP_MAPPING, payload["docker_publish"])
        self.assertIn(DOCKER_UDP_MAPPING, payload["docker_publish"])
        self.assertFalse(payload["mutates_config"])
        self.assertIn("ai-node-01", payload["known_servers"])

    def test_gateway_hooks_cli_json(self) -> None:
        code, output = self.capture(["--json", "gateway", "hooks"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        names = {hook["name"] for hook in payload["hooks"]}
        self.assertIn("codeproject-ai-mesh", names)

    def test_gateway_tui_flag_has_no_required_subcommand_parse_error(self) -> None:
        import argparse

        parser = __import__("fnpqnn_gateway_mvp.cli", fromlist=["build_parser"]).build_parser()
        args = parser.parse_args(["--tui"])
        self.assertTrue(args.tui)
        self.assertIsNone(args.section)

    def test_gateway_run_dry_run_does_not_execute(self) -> None:
        code, output = self.capture(["gateway", "run", "--hook", "simulator", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("dry-run", output)
        self.assertIn("fnp-qnn", output)

    def test_qlc_submit_dry_run_validates_and_fingerprints_bundle(self) -> None:
        payload = qlc_submit(_qlc_workflow_bundle(), dry_run=True, simulator_url="http://localhost:8000")

        self.assertTrue(payload["success"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["schema"], "ffed.qlc.gateway_submission.v1")
        self.assertEqual(payload["simulator_status"], "not_run")
        self.assertFalse(payload["raw_payload_echoed"])
        self.assertEqual(payload["loop_receipt"]["schema"], "ffed.qlc.gateway_celebrum_loop_receipt.v1")
        self.assertIn("swop_level:high", payload["datadog_tags"])

    def test_qlc_submit_rejects_raw_secret_or_media_fields(self) -> None:
        bundle = _qlc_workflow_bundle()
        bundle["gateway_submission"]["mesh_payload"]["raw_image"] = "not-allowed"

        with self.assertRaises(ValueError):
            extract_gateway_submission(bundle)

    def test_qlc_submit_accepts_shared_contract_fixture(self) -> None:
        bundle = json.loads((FIXTURE_ROOT / "qlc_workflow_image.json").read_text(encoding="utf-8"))

        payload = qlc_submit(bundle, dry_run=True, simulator_url="http://localhost:8000")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["gateway_status"], "dry_run")
        self.assertEqual(bundle["contract_version"], "qlc-wiring-contract.v2")
        self.assertEqual(bundle["gateway_submission"]["contract_version"], "qlc-wiring-contract.v2")
        self.assertEqual(payload["submission_fingerprint"], payload["loop_receipt"]["fingerprints"]["gateway_submission"])

    def test_qlc_submit_rejects_shared_forbidden_fixture(self) -> None:
        bundle = json.loads((FIXTURE_ROOT / "qlc_workflow_forbidden_raw.json").read_text(encoding="utf-8"))

        with self.assertRaises(ValueError):
            qlc_submit(bundle, dry_run=True)

    def test_qlc_submit_rejects_invalid_timeout(self) -> None:
        with self.assertRaises(ValueError):
            qlc_submit(_qlc_workflow_bundle(), dry_run=True, timeout=0)

    def test_qlc_submit_rejects_non_loopback_simulator_url(self) -> None:
        blocked_urls = [
            "file:///etc/passwd",
            "http://example.com:8000",
            "https://192.168.1.10:8000",
            "http://user:pass@localhost:8000",
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    qlc_submit(_qlc_workflow_bundle(), dry_run=True, simulator_url=url)

    def test_qlc_submit_can_emit_metrics_with_redacted_tags(self) -> None:
        emitted: list[tuple[str, tuple[str, ...]]] = []

        def fake_emit(event: str, tags: tuple[str, ...]) -> bool:
            emitted.append((event, tags))
            return True

        import fnpqnn_gateway_mvp.qlc_submit as qlc_submit_module

        original = qlc_submit_module.emit_gateway_submit_counter
        qlc_submit_module.emit_gateway_submit_counter = fake_emit
        try:
            payload = qlc_submit(_qlc_workflow_bundle(), dry_run=True, emit_metrics=True)
        finally:
            qlc_submit_module.emit_gateway_submit_counter = original

        self.assertTrue(payload["success"])
        self.assertEqual(emitted[0][0], "submit_ok")
        self.assertIn("swop_level:high", emitted[0][1])

    def test_dogstatsd_sanitizer_rejects_injection_delimiters_and_bounds_length(self) -> None:
        unsafe = "metric|c\nsecond:tag,another" + ("x" * 200)
        safe = sanitize_metric_token(unsafe)

        self.assertNotIn("|", safe)
        self.assertNotIn("\n", safe)
        self.assertNotIn(":", safe)
        self.assertNotIn(",", safe)
        self.assertLessEqual(len(safe), 120)

    def test_openclaw_env_loader_reports_presence_without_values(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("E2B_API_KEY=test-secret-value\nDD_API_KEY=dd-secret-value\n", encoding="utf-8")
            payload = load_openclaw_tool_env(env_path, keys=("E2B_API_KEY", "DD_API_KEY"))

        self.assertTrue(payload["success"])
        self.assertEqual(payload["presence"], {"E2B_API_KEY": True, "DD_API_KEY": True})
        self.assertFalse(payload["raw_values_printed"])
        self.assertNotIn("test-secret-value", json.dumps(payload))

    def test_qlc_tool_readiness_reports_redacted_status(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "E2B_API_KEY=e2b-secret-value\nDATADOG_API_KEY=dd-secret-value\nDD_DOGSTATSD_HOST=127.0.0.1\nDD_DOGSTATSD_PORT=8125\n",
                encoding="utf-8",
            )
            payload = qlc_tool_readiness(env_path)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema"], "ffed.qlc.tool_readiness_status.v1")
        self.assertTrue(payload["e2b_key_present"])
        self.assertTrue(payload["datadog_key_present"])
        self.assertTrue(payload["dogstatsd_config_present"])
        self.assertFalse(payload["raw_values_printed"])
        self.assertNotIn("secret-value", json.dumps(payload))

    def test_gateway_loop_receipt_compacts_simulator_response(self) -> None:
        receipt = build_gateway_loop_receipt(
            _qlc_workflow_bundle(),
            {"status": "ok", "runtime": {"feature_dimension": 4}},
        )

        self.assertEqual(receipt["schema"], "ffed.qlc.gateway_celebrum_loop_receipt.v1")
        self.assertEqual(receipt["route_action"], "submit_to_cerebrum")
        self.assertIn("simulator_result", receipt["fingerprints"])
        self.assertFalse(receipt["raw_payload_embedded"])

    def test_qlc_submit_posts_to_mock_cerebrum_runtime(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = self.rfile.read(int(self.headers.get("content-length", "0")))
                payload = json.loads(body.decode("utf-8"))
                self.server.received_path = self.path  # type: ignore[attr-defined]
                self.server.received_raw_echo = "raw_image" in json.dumps(payload)  # type: ignore[attr-defined]
                response = {
                    "status": "ok",
                    "runtime": {"feature_dimension": 4, "qlc_runtime": {"schema": "ffed.qlc.runtime_normalized_context.v1"}},
                    "persistence": {"snapshot": "mock"},
                }
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = qlc_submit(_qlc_workflow_bundle(), simulator_url=f"http://127.0.0.1:{server.server_port}", timeout=3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["gateway_status"], "accepted")
        self.assertEqual(payload["simulator_status"], "ok")
        self.assertEqual(server.received_path, "/cerebrum/runtime/run")  # type: ignore[attr-defined]
        self.assertFalse(server.received_raw_echo)  # type: ignore[attr-defined]
        self.assertFalse(payload["raw_payload_echoed"])
        self.assertIn("response_fingerprint", payload)

    def test_qlc_submit_unreachable_runtime_returns_compact_failure(self) -> None:
        payload = qlc_submit(_qlc_workflow_bundle(), simulator_url="http://127.0.0.1:9", timeout=1)

        self.assertFalse(payload["success"])
        self.assertEqual(payload["gateway_status"], "submit_failed")
        self.assertEqual(payload["simulator_status"], "submit_failed")
        self.assertIn("error_type", payload)
        self.assertLessEqual(len(payload["error"]), 180)
        self.assertFalse(payload["raw_payload_echoed"])

    def test_gateway_qlc_submit_cli_dry_run(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "qlc-bundle.json"
            bundle_path.write_text(json.dumps(_qlc_workflow_bundle()), encoding="utf-8")

            code, output = self.capture([
                "--json",
                "gateway",
                "qlc-readiness",
                "--env-file",
                str(bundle_path),
            ])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["schema"], "ffed.qlc.tool_readiness_status.v1")
        self.assertFalse(payload["raw_values_printed"])

    def test_gateway_qlc_readiness_cli_reports_redacted_status(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "qlc-bundle.json"
            bundle_path.write_text(json.dumps(_qlc_workflow_bundle()), encoding="utf-8")

            code, output = self.capture([
                "--json",
                "gateway",
                "qlc-submit",
                "--bundle",
                str(bundle_path),
                "--dry-run",
                "--e2b-enabled",
            ])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["dry_run"])
        self.assertIn("e2b_enabled:true", payload["datadog_tags"])

    def test_unreachable_url_returns_support_action(self) -> None:
        payload = status("http://127.0.0.1:9", timeout=0.2)
        self.assertFalse(payload["success"])
        self.assertIn("Start CodeProject.AI Server", str(payload["next_step"]))

    def test_runner_does_not_use_shell_true(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runner_source = (root / "fnpqnn_gateway_mvp" / "runner.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", runner_source)

    def test_codex_fingerprint_accept_routes_to_codex_hook(self) -> None:
        payload = activation_plan("codex", "fp-codex-123", workspace=".", accept_fingerprint=True)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["route"]["auth_provider"], "openai")
        self.assertEqual(payload["gates"]["runtime_gate"]["hook"], "codex")
        self.assertTrue(payload["gates"]["native_handoff_gate"]["agent_stays_native"])
        self.assertIn("fnpqnn gateway hooks", payload["gates"]["native_handoff_gate"]["simulator_capabilities"])

    def test_copilot_fingerprint_keeps_simulator_hook(self) -> None:
        route = route_for_tool("github-copilot")
        self.assertTrue(route.support_only)
        payload = activation_plan("github-copilot", "fp-copilot-123", workspace=".", accept_fingerprint=True)
        self.assertEqual(payload["route"]["auth_provider"], "github-copilot")
        self.assertEqual(payload["gates"]["runtime_gate"]["hook"], "simulator")
        self.assertTrue(payload["gates"]["runtime_gate"]["support_only"])

    def test_fingerprint_without_acceptance_is_blocked(self) -> None:
        payload = activation_plan("gemini", "fp-gemini-123", workspace=".", accept_fingerprint=False)
        self.assertFalse(payload["success"])
        self.assertIn("Fingerprint must be provided", payload["blocked_reason"])

    def test_activation_write_creates_gateway_state(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = activate("ollama-cloud", "fp-ollama-123", workspace=tmp, accept_fingerprint=True, write=True)
            self.assertTrue(payload["success"])
            self.assertTrue(Path(payload["paths"]["activation"]).exists())
            self.assertTrue(Path(payload["paths"]["agents"]).exists())
            agents = Path(payload["paths"]["agents"]).read_text(encoding="utf-8")
            self.assertIn("Native Takeover", agents)

    def test_bootstrap_natural_writes_activation_and_bootstrap_state(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = bootstrap("natural", "fp-natural", workspace=tmp, accept_fingerprint=True)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["runtime_hook"], "simulator")
            self.assertTrue(Path(payload["paths"]["activation"]).exists())
            self.assertTrue(Path(payload["paths"]["bootstrap"]).exists())
            state = load_bootstrap_state(tmp)
            self.assertEqual(state["profile"]["name"], "natural")
            self.assertEqual(state["runtime_hook"], "simulator")

    def test_bootstrap_profiles_resolve_expected_runtime_hooks(self) -> None:
        expected = {
            "codex": "codex",
            "antigravity": "antigravity",
            "ollama-cloud": "ollama-cloud",
            "openclaw": "openclaw",
        }
        for profile, hook in expected.items():
            with self.subTest(profile=profile):
                payload = build_bootstrap_plan(profile, f"fp-{profile}", accept_fingerprint=True)
                self.assertTrue(payload["success"])
                self.assertEqual(payload["runtime_hook"], hook)
                self.assertIn("fnp-qnn", payload["command"])

    def test_bootstrap_vscode_keeps_copilot_support_and_codeproject_tunnel(self) -> None:
        payload = build_bootstrap_plan(
            "vscode",
            "fp-vscode",
            accept_fingerprint=True,
            codeproject_url="localhost:32168",
        )
        self.assertTrue(payload["success"])
        self.assertEqual(payload["activation"]["route"]["tool"], "github-copilot")
        self.assertTrue(payload["activation"]["route"]["support_only"])
        self.assertEqual(payload["runtime_hook"], "simulator")
        self.assertEqual(payload["support_checks"]["codeproject_tunnel"]["url"], "http://localhost:32168")

    def test_bootstrap_docker_kit_dry_run_command(self) -> None:
        payload = build_bootstrap_plan("docker-kit", "fp-docker", accept_fingerprint=True)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["profile"]["name"], "docker-kit")
        self.assertEqual(payload["command"], ["docker", "compose", "up", "--build", "simulator-api", "simulator-panel"])

    def test_gateway_start_dry_run_uses_last_bootstrap_state(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bootstrap("natural", "fp-natural", workspace=tmp, accept_fingerprint=True)
            code, output = self.capture(["--json", "gateway", "start", "--workspace", tmp, "--dry-run"])
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["profile"]["name"], "natural")
            self.assertEqual(payload["runtime_hook"], "simulator")
            self.assertIn("fnp-qnn", payload["command"])

    def test_gateway_run_profile_natural_dry_run(self) -> None:
        code, output = self.capture(["--json", "gateway", "run", "--profile", "natural", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["profile"]["name"], "natural")
        self.assertEqual(payload["runtime_hook"], "simulator")
        self.assertIn("fnp-qnn", payload["command"])

    def test_gateway_bootstrap_profiles_cli(self) -> None:
        code, output = self.capture(["--json", "gateway", "bootstrap-profiles"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        names = {profile["name"] for profile in payload["profiles"]}
        self.assertTrue({"natural", "vscode", "ollama-cloud", "openclaw", "cloud-kit", "docker-kit"}.issubset(names))

    def test_gateway_bootstrap_profile_dry_run_can_omit_fingerprint(self) -> None:
        code, output = self.capture(["--json", "gateway", "bootstrap", "--profile", "codex", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["profile"]["name"], "codex")
        self.assertEqual(payload["activation"]["fingerprint"], "dry-run-codex")

    def test_gateway_activate_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "gateway",
            "activate",
            "--tool",
            "codex",
            "--fingerprint",
            "fp-codex-123",
            "--accept-fingerprint",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["gates"]["runtime_gate"]["hook"], "codex")

    def test_auth_fingerprint_accept_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "auth",
            "fingerprint",
            "accept",
            "--tool",
            "codeproject-ai",
            "--fingerprint",
            "fp-codeproject-123",
            "--codeproject-url",
            "http://localhost:32168",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["gates"]["runtime_gate"]["hook"], "codeproject-ai")
        self.assertEqual(payload["codeproject_url"], "http://localhost:32168")

    def test_model_provider_switch_is_web_auth_first_and_secret_safe(self) -> None:
        payload = build_model_provider_switch(tool="codex", fingerprint="fp-codex", workspace=".")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider"]["provider"], "openai")
        self.assertEqual(payload["selected_auth_source"], "web-auth")
        self.assertFalse(payload["managed_env_policy"]["user_must_edit_env"])
        self.assertFalse(payload["managed_env_policy"]["user_must_paste_token"])
        self.assertFalse(payload["managed_env_policy"]["dotenv_read_for_switch"])
        self.assertFalse(payload["auth_signals"]["secret_values_included"])
        provider_text = " ".join(payload["provider"]["instructions"]).lower()
        auth_text = " ".join(payload["auth_status"]["instructions"]).lower()
        self.assertNotIn("set ", provider_text)
        self.assertNotIn("paste", provider_text)
        self.assertNotIn("edit", provider_text)
        self.assertNotIn("api_key", auth_text)
        self.assertNotIn("paste", auth_text)

    def test_model_provider_switch_can_use_last_bootstrap(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bootstrap("antigravity", "fp-google", workspace=tmp, accept_fingerprint=True)
            payload = model_provider_switch(workspace=tmp, last=True)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["fingerprint"], "fp-google")
            self.assertEqual(payload["provider"]["provider"], "google")
            self.assertEqual(payload["selected_auth_source"], "web-auth")

    def test_auth_model_switch_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "auth",
            "model-switch",
            "--tool",
            "ollama-cloud",
            "--fingerprint",
            "fp-ollama",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["provider"]["provider"], "ollama")
        self.assertEqual(payload["selected_auth_source"], "web-auth")

    def test_function_provider_switch_alias_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "function",
            "provider-switch",
            "--tool",
            "github-copilot",
            "--fingerprint",
            "fp-copilot",
            "--source",
            "petit-yolo-instructions",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["selected_auth_source"], "petit-yolo-instructions")
        self.assertEqual(payload["fallback"]["name"], "petit-yolo-instructions")

    def test_model_provider_switch_write_creates_gateway_state_only(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = model_provider_switch(tool="codex", fingerprint="fp-codex", workspace=tmp, write=True)
            self.assertTrue(payload["success"])
            path = Path(payload["paths"]["model_provider"])
            self.assertTrue(path.exists())
            self.assertFalse((Path(tmp) / ".env").exists())

    def test_auth_login_systems_cover_chosen_bootstrap_systems(self) -> None:
        systems = {item["system"] for item in list_auth_login_systems()}
        expected = {
            "natural",
            "codex",
            "antigravity",
            "vscode",
            "ollama-cloud",
            "openclaw",
            "cloud-kit",
            "docker-kit",
            "codeproject-ai",
            "e2b",
            "datadog",
            "google",
            "github",
            "docker",
        }
        self.assertTrue(expected.issubset(systems))

    def test_auth_login_is_web_auth_first_and_secret_safe(self) -> None:
        payload = auth_login("codex", fingerprint="fp-codex", accept_fingerprint=True)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "fingerprint-accepted")
        self.assertEqual(payload["auth_flow"]["primary"], "web-auth")
        self.assertFalse(payload["policy"]["user_must_paste_secret"])
        self.assertFalse(payload["policy"]["user_must_edit_env"])
        self.assertFalse(payload["policy"]["dotenv_read"])
        self.assertFalse(payload["policy"]["dotenv_write"])
        self.assertEqual(payload["provider_switch"]["selected_auth_source"], "web-auth")
        self.assertTrue(payload["validation"]["success"])

    def test_auth_login_all_returns_each_system(self) -> None:
        payload = auth_login("all")
        self.assertTrue(payload["success"])
        systems = {item["system"]["system"] for item in payload["systems"]}
        self.assertIn("cloud-kit", systems)
        self.assertIn("docker-kit", systems)
        self.assertIn("datadog", systems)

    def test_auth_login_write_creates_only_gateway_login_state(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = auth_login("codex", workspace=tmp, fingerprint="fp-codex", accept_fingerprint=True, write=True)
            self.assertTrue(payload["success"])
            self.assertTrue(Path(payload["paths"]["auth_login"]).exists())
            self.assertFalse((Path(tmp) / ".env").exists())

    def test_auth_login_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "auth",
            "login",
            "--system",
            "cloud-kit",
            "--fingerprint",
            "fp-cloud",
            "--accept-fingerprint",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["system"]["provider"], "e2b")
        self.assertEqual(payload["auth_flow"]["primary"], "web-auth")
        self.assertTrue(payload["validation"]["success"])

    def test_function_auth_login_alias_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "function",
            "auth-login",
            "--system",
            "vscode",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["system"]["provider"], "github-copilot")
        self.assertTrue(payload["system"]["support_only"])

    def test_explicit_web_auth_accounts_have_https_hooks(self) -> None:
        expected = {
            "e2b": "https://e2b.dev/dashboard",
            "datadog": "https://app.datadoghq.com/account/login",
            "google": "https://accounts.google.com/",
            "github": "https://github.com/login",
            "docker": "https://app.docker.com/sign-in",
        }
        for system, url in expected.items():
            with self.subTest(system=system):
                payload = auth_login(system)
                self.assertTrue(payload["success"])
                self.assertEqual(payload["web_auth_hook"]["url"], url)
                self.assertTrue(payload["validation"]["success"])
                self.assertFalse(payload["web_auth_hook"]["stores_secret"])

    def test_auth_login_open_browser_uses_system_url(self) -> None:
        from unittest.mock import patch

        with patch("fnpqnn_gateway_mvp.web_auth_login.webbrowser.open", return_value=True) as opened:
            payload = auth_login("datadog", open_browser=True)
        self.assertTrue(payload["auth_flow"]["browser_opened"])
        opened.assert_called_once_with("https://app.datadoghq.com/account/login")

    def test_capability_map_keeps_codex_and_simulator_separate(self) -> None:
        payload = capability_map("codex", workspace=".")
        self.assertEqual(payload["bridge_model"], "non-absorbing capability bridge")
        self.assertIn("Codex", " ".join(payload["native_tool_owns"]))
        self.assertIn("simulator", " ".join(payload["simulator_owns"]).lower())
        self.assertIn("The simulator does not become the provider tool.", payload["non_absorption_rules"])

    def test_skill_request_describes_native_handoff(self) -> None:
        payload = skill_request("codex", "simulator gate builder", "Create a skill that designs simulator gates.", workspace=".")
        self.assertTrue(payload["success"])
        self.assertTrue(payload["native_handoff"]["native_tool_must_execute_own_skills"])
        self.assertEqual(payload["native_handoff"]["runtime_hook"], "codex")
        self.assertIn("Non-Absorption Rule", payload["markdown_preview"])

    def test_skill_request_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "gateway",
            "skill-request",
            "--tool",
            "codex",
            "--name",
            "simulator gate builder",
            "--goal",
            "Create gates for the simulator using native Codex skills.",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["tool"], "codex")
        self.assertTrue(payload["dry_run"])

    def test_skill_entry_builds_entry_exit_contract(self) -> None:
        payload = build_skill_entry(
            name="Test Skill",
            goal="Create a test skill contract.",
            profile="codex",
            workspace=".",
        )
        self.assertTrue(payload["success"])
        self.assertEqual(payload["skill_name"], "test-skill")
        self.assertEqual(payload["contract"]["bootstrap_profile"], "codex")
        self.assertEqual(payload["contract"]["tool"], "codex")
        self.assertIn("do not expose secrets", payload["contract"]["forbidden_actions"])
        self.assertTrue(payload["paths"]["entry_json"].endswith(".fnpqnn_gateway\\skill_entries\\test-skill.json") or payload["paths"]["entry_json"].endswith(".fnpqnn_gateway/skill_entries/test-skill.json"))

    def test_skill_entry_write_creates_entry_and_exit_paths(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_skill_entry(
                name="Test Skill",
                goal="Create a test skill contract.",
                profile="codex",
                workspace=tmp,
            )
            result = write_skill_entry(payload)
            self.assertFalse(result["dry_run"])
            self.assertTrue(Path(payload["paths"]["entry_json"]).exists())
            self.assertTrue(Path(payload["paths"]["entry_markdown"]).exists())
            self.assertTrue(Path(payload["paths"]["exit_json"]).exists())
            self.assertTrue(Path(payload["paths"]["exit_markdown"]).exists())

    def test_skill_creator_plan_uses_last_bootstrap(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bootstrap("antigravity", "fp-gemini", workspace=tmp, accept_fingerprint=True)
            payload = build_skill_creator_plan(
                name="Gemini Skill",
                goal="Create a Gemini companion skill.",
                workspace=tmp,
                last=True,
            )
            self.assertTrue(payload["success"])
            self.assertEqual(payload["bootstrap_route"]["profile"], "antigravity")
            self.assertEqual(payload["bootstrap_route"]["fingerprint"], "fp-gemini")
            self.assertIn("SKILL.md", payload["creator_plan"]["skill_md"])
            self.assertTrue(payload["creator_plan"]["skill_creator_rules"]["skill_md_required"])

    def test_skill_creator_write_can_create_skill_files_when_requested(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_skill_creator_plan(
                name="Created Skill",
                goal="Create a real local skill file.",
                profile="natural",
                workspace=tmp,
                output_path=Path(tmp) / "skills",
                resources=["scripts"],
            )
            result = write_skill_creator_plan(payload, create_skill_files=True)
            skill_md = Path(payload["creator_plan"]["skill_md"])
            self.assertTrue(skill_md.exists())
            content = skill_md.read_text(encoding="utf-8")
            self.assertIn("name: created-skill", content)
            self.assertTrue((skill_md.parent / "scripts").exists())

    def test_gateway_skill_entry_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "gateway",
            "skill-entry",
            "--name",
            "test-skill",
            "--goal",
            "Create a test skill contract",
            "--profile",
            "codex",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["skill_name"], "test-skill")
        self.assertEqual(payload["bootstrap_route"]["profile"], "codex")

    def test_gateway_skill_create_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "gateway",
            "skill-create",
            "--name",
            "test-skill",
            "--goal",
            "Create a test skill contract",
            "--profile",
            "codex",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["skill_name"], "test-skill")
        self.assertIn("creator_plan", payload)

    def test_function_skill_creator_alias_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "function",
            "skill-creator",
            "--name",
            "test-skill",
            "--goal",
            "Create a test skill contract",
            "--profile",
            "codex",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["bootstrap_route"]["tool"], "codex")
        self.assertIn("exit_contract", payload)

    def test_deepsearch_ollama_cloud_uses_native_route(self) -> None:
        payload = build_deepsearch_skill(query="validate simulator research", system="ollama-cloud")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["search_route"]["route"], "ollama-cloud-web-search")
        self.assertFalse(payload["search_route"]["fallback_used"])
        self.assertTrue(payload["policy"]["no_generic_scraper_first"])
        self.assertFalse(payload["raw_secret_stored"])

    def test_deepsearch_non_search_provider_falls_back_to_antigravity(self) -> None:
        payload = build_deepsearch_skill(query="datadog account research", system="datadog")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["search_route"]["route"], "antigravity-gemini-google-search")
        self.assertTrue(payload["search_route"]["fallback_used"])
        self.assertEqual(payload["search_route"]["provider"], "google")

    def test_deepsearch_last_auth_uses_latest_written_authlog(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            auth_login("docker", workspace=tmp, fingerprint="fp-docker", accept_fingerprint=True, write=True)
            auth_login("google", workspace=tmp, fingerprint="fp-google", accept_fingerprint=True, write=True)
            payload = build_deepsearch_skill(query="latest authenticated search", workspace=tmp, last_auth=True)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["authlog_source"], "last-auth")
            self.assertEqual(payload["search_route"]["selected_provider"], "google")
            self.assertFalse(payload["search_route"]["fallback_used"])
            self.assertEqual(payload["fingerprint_ref"], "fp-google")

    def test_deepsearch_write_creates_only_gateway_contract(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_deepsearch_skill(query="Create a cited report", workspace=tmp, system="antigravity")
            result = write_deepsearch_skill(payload)
            self.assertFalse(result["dry_run"])
            self.assertTrue(Path(payload["paths"]["contract_json"]).exists())
            self.assertTrue(Path(payload["paths"]["contract_markdown"]).exists())
            self.assertFalse((Path(tmp) / ".env").exists())
            content = Path(payload["paths"]["contract_json"]).read_text(encoding="utf-8")
            self.assertNotIn("api_key", content.lower())
            saved = json.loads(content)
            self.assertFalse(saved["raw_secret_stored"])
            self.assertFalse(saved["policy"]["raw_secret_stored"])

    def test_gateway_deepsearch_skill_cli_dry_run(self) -> None:
        code, output = self.capture([
            "--json",
            "gateway",
            "deepsearch-skill",
            "--query",
            "research validation",
            "--system",
            "ollama-cloud",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["search_route"]["route"], "ollama-cloud-web-search")
        self.assertIn("simulator_skill", payload)

    def test_function_deepsearch_alias_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "function",
            "deepsearch",
            "--query",
            "research validation",
            "--system",
            "docker",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["search_route"]["fallback_used"])
        self.assertEqual(payload["search_route"]["route"], "antigravity-gemini-google-search")

    def test_capability_map_cli(self) -> None:
        code, output = self.capture(["--json", "gateway", "capability-map", "--tool", "github-copilot"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["runtime_hook"], "simulator")
        self.assertIn("Copilot", " ".join(payload["native_tool_owns"]))

    def test_requested_surfaces_have_activation_and_capability_routes(self) -> None:
        expected = {
            "antigravity": ("google", "antigravity"),
            "codeproject-ai-server": (None, "codeproject-ai-server"),
            "github-copilot": ("github-copilot", "simulator"),
            "ollama": ("ollama", "ollama"),
            "openclaw": (None, "openclaw"),
        }
        for tool, (provider, hook) in expected.items():
            with self.subTest(tool=tool):
                plan = activation_plan(tool, f"fp-{tool}", workspace=".", accept_fingerprint=True)
                bridge = capability_map(tool, workspace=".")
                self.assertEqual(plan["route"]["auth_provider"], provider)
                self.assertEqual(plan["gates"]["runtime_gate"]["hook"], hook)
                self.assertEqual(bridge["runtime_hook"], hook)
                self.assertEqual(bridge["bridge_model"], "non-absorbing capability bridge")

    def test_codeproject_yolo_uses_official_routes(self) -> None:
        payload = yolo_probe("http://localhost:32168", dry_run=True)
        self.assertEqual(payload["method"], "POST")
        self.assertEqual(payload["file_field"], "image")
        self.assertIn("/v1/vision/detection", payload["routes"])
        self.assertIn("/v1/vision/custom/list", payload["routes"])
        self.assertIn("/v1/vision/custom/<model-name>", payload["routes"])

    def test_codeproject_yolo_training_module_is_explicit(self) -> None:
        payload = yolo_training_probe("http://localhost:32168", dry_run=True)
        self.assertEqual(payload["module"]["module_id"], "TrainingObjectDetectionYOLOv5")
        self.assertEqual(payload["module"]["name"], "Training for YoloV5 6.2")
        self.assertEqual(YOLO_TRAINING_MODULE["version"], "1.7.0")
        self.assertEqual(payload["routes"]["create_dataset"], "/v1/train/create_dataset")
        self.assertEqual(payload["routes"]["train_model"], "/v1/train/train_model")
        self.assertEqual(payload["routes"]["model_info"], "/v1/train/model_info")

    def test_codeproject_yolo_training_cli_dry_run(self) -> None:
        code, output = self.capture(["--json", "codeproject", "yolo-training-status", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["module"]["name"], "Training for YoloV5 6.2")
        self.assertIn("train_model", payload["routes"])

    def test_obsidian_bridge_writes_and_queries_notes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            init_payload = init_obsidian("codex", workspace=tmp, write=True)
            self.assertTrue(init_payload["success"])
            record_payload = record_note(
                "codex",
                "YOLO Cerebrum Gate",
                "Map YOLO detections into Cerebrum runtime gate events.",
                workspace=tmp,
                tags=["yolo", "cerebrum"],
                write=True,
            )
            self.assertTrue(record_payload["success"])
            self.assertIn("fnpqnn_t", record_payload["neutrosophic_frontmatter"])
            self.assertEqual(record_payload["neutrosophic_frontmatter"]["fnpqnn_gate"], "p114")
            query_payload = query_notes("yolo cerebrum", workspace=tmp)
            self.assertEqual(len(query_payload["results"]), 1)
            self.assertIn("YOLO Cerebrum Gate", query_payload["results"][0]["title"])

    def test_p114_consensus_cli_gate(self) -> None:
        payload = p114_consensus(["verified evidence passed", "partial risk pending"])
        if payload["status"] == "disabled":
            self.skipTest(payload["metadata"].get("message", "p114 pluginpack disabled"))
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["plugin_id"], "p114_ffed_neutrosophic_consensus")
        self.assertIn("consensus", payload)
        self.assertFalse(payload["raw_token_stored"])

    def test_p114_consensus_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "memory",
            "p114-consensus",
            "--item",
            "verified evidence passed",
            "--item",
            "partial risk pending",
        ])
        payload = json.loads(output)
        if payload["status"] == "disabled":
            self.skipTest(payload["metadata"].get("message", "p114 pluginpack disabled"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["plugin_id"], "p114_ffed_neutrosophic_consensus")

    def test_obsidian_cli_dry_run(self) -> None:
        code, output = self.capture(["--json", "memory", "obsidian-init", "--tool", "openclaw", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["vault_semantics"], "obsidian-markdown-jsonl-rag")
        self.assertFalse(payload["memory_contract"]["private_tool_store_scraping"])
        self.assertEqual(payload["lvfm_stream_contract"]["target_layer"], "FNP-QNN LVFMRuntimeGraph via Cerebrum runtime")

    def test_obsidian_lvfm_stream_builds_cerebrum_payload(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            init_obsidian("codeproject-ai-server", workspace=tmp, write=True)
            record_note(
                "codeproject-ai-server",
                "CodeProject YOLO creek",
                "YOLO detection should feed the LVFM river through Cerebrum runtime.",
                workspace=tmp,
                tags=["yolo", "lvfm"],
                write=True,
            )
            payload = lvfm_stream("yolo lvfm", workspace=tmp)
            self.assertEqual(payload["target_layer"], "lvfm-runtime-river")
            self.assertEqual(payload["cerebrum_ingest_endpoint"], "POST /cerebrum/runtime/ingest")
            self.assertEqual(len(payload["cerebrum_payload"]["memories"]), 1)
            self.assertEqual(payload["events"][0]["metadata"]["bridge"], "obsidian-creek-to-lvfm-river")
            self.assertIn("neutrosophic_gate", payload["events"][0]["metadata"])
            self.assertIn("neutrosophic_frontmatter", payload["events"][0]["metadata"])

    def test_obsidian_lvfm_stream_cli(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            init_obsidian("codex", workspace=tmp, write=True)
            record_note("codex", "LVFM note", "A note for LVFM stream.", workspace=tmp, tags=["lvfm"], write=True)
            code, output = self.capture([
                "--json",
                "memory",
                "obsidian-lvfm-stream",
                "--query",
                "lvfm",
                "--workspace",
                tmp,
            ])
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["stream"], "obsidian-admission-creek")

    def test_e2b_status_is_secret_safe(self) -> None:
        payload = e2b_status()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider"], "e2b")
        self.assertIn("e2b_code_interpreter", payload["packages"])
        self.assertFalse(payload["raw_token_stored"])

    def test_e2b_ingest_plan_links_cloud_to_obsidian_and_lvfm(self) -> None:
        payload = e2b_ingest_plan("codex", "https://example.com/data.csv", "External Data")
        self.assertTrue(payload["success"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["tool"], "codex")
        self.assertIn("Obsidian creek feeds LVFM stream", payload["pipeline"])
        self.assertTrue(payload["boundaries"]["no_raw_tokens"])
        self.assertIn("obsidian-record", payload["commands"]["admit_to_obsidian"])
        self.assertIn("obsidian-lvfm-stream", payload["commands"]["feed_lvfm"])

    def test_e2b_ingest_plan_cli(self) -> None:
        code, output = self.capture([
            "--json",
            "cloud",
            "e2b-ingest-plan",
            "--tool",
            "openclaw",
            "--source",
            "https://example.com/data.csv",
            "--title",
            "External Data",
            "--dry-run",
        ])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["tool"], "openclaw")
        self.assertEqual(payload["runtime_hook"], "openclaw")
        self.assertTrue(payload["boundaries"]["sandbox_required_for_untrusted_code"])

    def test_e2b_real_smoke_when_openclaw_key_is_available(self) -> None:
        env_file = Path.home() / ".openclaw" / "workspace" / ".env"
        if not env_file.exists():
            self.skipTest("OpenClaw .env is not available")
        has_key = any(
            line.strip().startswith("E2B_API_KEY=") and bool(line.split("=", 1)[1].strip())
            for line in env_file.read_text(encoding="utf-8").splitlines()
        )
        if not has_key:
            self.skipTest("E2B_API_KEY is not present in OpenClaw .env")
        payload = e2b_smoke(env_file)
        self.assertTrue(payload["success"], payload)
        self.assertTrue(payload["stdout_contains_expected_marker"])
        self.assertFalse(payload["raw_token_stored"])


if __name__ == "__main__":
    unittest.main()
