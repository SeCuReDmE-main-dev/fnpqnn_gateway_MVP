from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest

from fnpqnn_gateway_mvp.cli import main
from fnpqnn_gateway_mvp.activation import activate, activation_plan, route_for_tool
from fnpqnn_gateway_mvp.capability_bridge import capability_map, skill_request
from fnpqnn_gateway_mvp.cloud_kit import e2b_ingest_plan, e2b_smoke, e2b_status
from fnpqnn_gateway_mvp.codeproject_client import DEFAULT_PROBE_ROUTES, YOLO_TRAINING_MODULE, status, yolo_probe, yolo_training_probe
from fnpqnn_gateway_mvp.codeproject_mesh import DOCKER_TCP_MAPPING, DOCKER_UDP_MAPPING, mesh_status
from fnpqnn_gateway_mvp.hooks import HOOKS
from fnpqnn_gateway_mvp.neutrosophic_gate import p114_consensus
from fnpqnn_gateway_mvp.obsidian_bridge import init_obsidian, lvfm_stream, query_notes, record_note
from fnpqnn_gateway_mvp.support import support_all
from fnpqnn_gateway_mvp.tunnel import tunnel_status


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
