from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest

from fnpqnn_gateway_mvp.cli import main
from fnpqnn_gateway_mvp.codeproject_client import DEFAULT_PROBE_ROUTES, status
from fnpqnn_gateway_mvp.codeproject_mesh import DOCKER_TCP_MAPPING, DOCKER_UDP_MAPPING, mesh_status
from fnpqnn_gateway_mvp.hooks import HOOKS
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
            "ollama-cloud",
            "agent-platform",
            "codeproject-ai",
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


if __name__ == "__main__":
    unittest.main()
