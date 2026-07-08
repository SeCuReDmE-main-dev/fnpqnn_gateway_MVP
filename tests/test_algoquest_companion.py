from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fnpqnn_gateway_mvp.algoquest_companion import (
    REQUIRED_APP_CHECKS,
    build_app_contract_check,
    build_gateway_install_sequence,
    build_metrics_envelope,
    build_qbit_intervention,
    build_session_role,
    build_student_learning_event,
    build_teacher_planning_event,
    companion_contract_plan,
    eleven_app_contract_check_plan,
    eleven_app_registration_plan,
    three_app_validation_fixture,
    validate_gateway_install_sequence,
    validate_metrics_envelope,
    validate_qbit_intervention,
    validate_session_role,
    validate_student_learning_event,
    validate_teacher_planning_event,
)
from fnpqnn_gateway_mvp.cli import main


class AlgoQuestCompanionContractTests(unittest.TestCase):
    def capture(self, argv: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, stream.getvalue()

    def test_gateway_install_sequence_enforces_doctor_offer_tool_order(self) -> None:
        payload = build_gateway_install_sequence(
            "visual-algorithm",
            doctor_status="passed",
            algoquest_offer_status="enable_for_suite",
            selected_tool_status="pending",
            role="student_minor",
        )

        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["install_order"], ["gateway_doctor", "algoquest_companion_offer", "selected_tool"])
        self.assertEqual(payload["decision"], "allow_selected_tool")
        event = payload["algoquest_event"]
        self.assertEqual(event["schema"], "securedme.education.student-learning-event.v1")
        self.assertEqual(event["app_slug"], "gateway")
        self.assertEqual(event["workflow"], "gateway_doctor_algoquest_offer")
        self.assertEqual(event["install_order"], ["gateway_doctor", "algoquest_companion_offer", "selected_tool"])
        self.assertTrue(event["artifact_ref"].startswith("gateway:install:"))
        self.assertTrue(event["requested_tool_ref"].startswith("tool:"))
        self.assertNotIn("visual-algorithm", repr(event))
        self.assertNotIn("fingerprint-redacted", repr(event))
        self.assertFalse(event["raw_secret_stored"])

    def test_gateway_install_sequence_blocks_tool_when_doctor_fails(self) -> None:
        payload = build_gateway_install_sequence(
            "visual-algorithm",
            doctor_status="failed",
            algoquest_offer_status="enable_for_this_tool",
            selected_tool_status="pending",
        )

        self.assertFalse(payload["success"])
        self.assertIn("doctor_before_tool", {error["code"] for error in payload["errors"]})
        self.assertEqual(payload["decision"], "block_selected_tool")

    def test_gateway_install_sequence_rejects_missing_algoquest_offer_status(self) -> None:
        payload = build_gateway_install_sequence("visual-algorithm", algoquest_offer_status="")

        self.assertFalse(payload["success"])
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("missing_field", codes)
        self.assertIn("algoquest_offer_status", codes)

    def test_session_role_blocks_student_minor_from_teacher_surface(self) -> None:
        session = build_session_role("student_minor", surface="teacher")

        self.assertFalse(session["success"])
        self.assertIn("role_surface_mismatch", {error["code"] for error in session["errors"]})

    def test_session_role_blocks_teacher_from_student_surface(self) -> None:
        session = build_session_role("teacher", surface="student")

        self.assertFalse(session["success"])
        self.assertIn("role_surface_mismatch", {error["code"] for error in session["errors"]})

    def test_session_role_rejects_expired_session(self) -> None:
        payload = build_session_role("student_adult", expires_at="2020-01-01T00:00:00+00:00")

        self.assertFalse(payload["success"])
        self.assertIn("session_expired", {error["code"] for error in payload["errors"]})

    def test_student_learning_event_rejects_student_name_and_raw_prompt(self) -> None:
        event = build_student_learning_event(
            "visual-algorithm",
            "artifact:pointer",
            skill_area="algorithm_design",
            difficulty_band="grade5-sec2",
            score=93,
        )
        event["student_name"] = "Do Not Store"
        event["raw_prompt"] = "Explain my whole private chat"

        errors = validate_student_learning_event(event)

        self.assertIn("forbidden_field", {error["code"] for error in errors})

    def test_teacher_planning_event_rejects_raw_student_data(self) -> None:
        event = build_teacher_planning_event(
            "algoquest",
            classroom_scope="classroom-redacted",
            aggregate_need="support_before_promotion",
            rubric_ref="rubric:algorithm_design",
            activity_ref="activity:algoquest",
        )
        event["student_id"] = "student-123"

        errors = validate_teacher_planning_event(event)

        self.assertIn("forbidden_field", {error["code"] for error in errors})

    def test_teacher_planning_event_requires_redaction_and_minimum_aggregation(self) -> None:
        event = build_teacher_planning_event(
            "algoquest",
            classroom_scope="single-student",
            aggregate_need="support",
            rubric_ref="rubric:algorithm_design",
            activity_ref="activity:algoquest",
            aggregation_count=1,
            redaction_status="raw",
        )

        self.assertFalse(event["success"])
        codes = {error["code"] for error in event["errors"]}
        self.assertIn("redaction_status", codes)
        self.assertIn("aggregation_minimum", codes)

    def test_metrics_reject_student_to_teacher_store(self) -> None:
        metric = build_metrics_envelope(
            "student",
            "visual-algorithm",
            "attempt_count",
            metric_store="teacher",
            dimensions={"score": 93, "threshold": 93},
        )

        self.assertFalse(metric["success"])
        self.assertIn("metrics_store_mismatch", {error["code"] for error in metric["errors"]})

    def test_metrics_reject_secret_like_dimension(self) -> None:
        metric = build_metrics_envelope(
            "teacher",
            "algoquest",
            "activity_completion_rate",
            metric_store="teacher",
            dimensions={"api_key": "not-allowed"},
        )

        errors = validate_metrics_envelope(metric)

        self.assertIn("forbidden_field", {error["code"] for error in errors})

    def test_qbit_cross_app_requires_consent(self) -> None:
        qbit = build_qbit_intervention(
            "student",
            trigger_reason="privacy_risk_detected",
            suggested_tool="vot-guardian",
            requires_consent=False,
        )

        self.assertFalse(qbit["success"])
        self.assertIn("cross_app_consent", {error["code"] for error in qbit["errors"]})

    def test_three_app_fixture_promotes_score_93_and_uses_artifact_pointer_only(self) -> None:
        payload = three_app_validation_fixture(score=93)

        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["apps"], ["visual-algorithm", "algoquest", "vot-guardian"])
        self.assertTrue(payload["promoted"])
        self.assertFalse(payload["guardian_pointer"]["raw_payload_embedded"])
        self.assertFalse(payload["guardian_pointer"]["raw_secret_stored"])
        self.assertEqual(payload["qbit_intervention"]["suggested_tool"], "vot-guardian")

    def test_three_app_fixture_rejects_score_below_93(self) -> None:
        payload = three_app_validation_fixture(score=92.99)

        self.assertFalse(payload["success"])
        self.assertFalse(payload["promoted"])
        self.assertEqual(payload["qbit_intervention"]["suggested_tool"], "algoquest")

    def test_eleven_app_registration_plan_excludes_algoquest_and_returns_11_apps(self) -> None:
        plan = eleven_app_registration_plan()

        self.assertTrue(plan["success"], plan)
        self.assertEqual(plan["app_count"], 11)
        self.assertNotIn("algoquest", {app["slug"] for app in plan["apps"]})
        self.assertIn("route_plan_dry_run", plan["required_checks_per_app"])

    def test_build_app_contract_check_validates_required_checks_for_one_app(self) -> None:
        payload = build_app_contract_check("visual-algorithm")

        self.assertTrue(payload["success"], payload)
        self.assertEqual(set(payload["required_checks"]), set(REQUIRED_APP_CHECKS))
        self.assertEqual(set(payload["check_results"]), set(REQUIRED_APP_CHECKS))
        self.assertTrue(all(payload["check_results"].values()), payload["check_results"])
        self.assertTrue(payload["route_plan"]["dry_run"])
        self.assertTrue(payload["route_plan"]["live_write_gated"])
        self.assertTrue(payload["secret_rejection"]["success"])
        self.assertEqual(payload["adapter_manifest"]["schema"], "securedme.education.algoquest-qbit-app-adapter.v1")
        self.assertTrue(payload["check_results"]["qbit_badge_asset_file"])
        self.assertTrue(payload["qbit_badge_asset_path"].endswith(".codex\\algoquest-qbit-assets\\algoquest-tiny-mark.png"))
        self.assertEqual(payload["install_sequence"]["install_order"], ["gateway_doctor", "algoquest_companion_offer", "selected_tool"])

    def test_build_app_contract_check_requires_app_side_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            payload = build_app_contract_check("visual-algorithm", suite_root=temp_root)

        self.assertFalse(payload["success"])
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("adapter_manifest_missing", codes)
        self.assertFalse(payload["check_results"]["adapter_map"])

    def test_build_app_contract_check_requires_declared_sdk_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            manifest_dir = Path(temp_root) / "VisualAlgorithmDesigner" / ".codex"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "algoquest-qbit-adapter.json").write_text(
                json.dumps(
                    {
                        "schema": "securedme.education.algoquest-qbit-app-adapter.v1",
                        "app_slug": "visual-algorithm",
                        "hub_slug": "algoquest",
                        "contract_version": "v1",
                        "required_checks": list(REQUIRED_APP_CHECKS),
                        "contracts": [
                            "securedme.education.gateway-install-sequence.v1",
                            "securedme.education.session-role.v1",
                            "securedme.education.student-learning-event.v1",
                            "securedme.education.metrics-envelope.v1",
                            "securedme.education.qbit-intervention.v1",
                        ],
                        "sdk_hook_path": "RaySight-frontend/src/services/algoQuestEventBridge.ts",
                        "sdk_hook_kind": "typescript",
                        "dry_run": True,
                        "raw_secret_stored": False,
                    }
                ),
                encoding="utf-8",
            )
            payload = build_app_contract_check("visual-algorithm", suite_root=temp_root)

        self.assertFalse(payload["success"])
        self.assertIn("sdk_hook_missing", {error["code"] for error in payload["errors"]})

    def test_build_app_contract_check_rejects_unknown_app(self) -> None:
        payload = build_app_contract_check("not-in-suite")

        self.assertFalse(payload["success"])
        self.assertIn("unknown_app", {error["code"] for error in payload["errors"]})

    def test_eleven_app_contract_check_plan_validates_each_non_hub_app(self) -> None:
        plan = eleven_app_contract_check_plan()

        self.assertTrue(plan["success"], plan)
        self.assertEqual(plan["app_count"], 11)
        self.assertEqual(plan["summary"]["passed"], 11)
        self.assertEqual(plan["summary"]["failed"], 0)
        self.assertNotIn("algoquest", {item["app"]["slug"] for item in plan["apps"]})
        for item in plan["apps"]:
            self.assertTrue(item["success"], item)
            self.assertTrue(all(item["check_results"].values()), item["check_results"])
            self.assertTrue(item["qbit_badge_asset_path"].endswith(".codex\\algoquest-qbit-assets\\algoquest-tiny-mark.png"))
            self.assertFalse(item["raw_secret_stored"])

    def test_companion_contract_plan_is_secret_safe_and_complete(self) -> None:
        plan = companion_contract_plan()

        self.assertTrue(plan["success"], plan)
        self.assertEqual(len(plan["contracts"]), 6)
        self.assertEqual(plan["eleven_app_registration"]["app_count"], 11)
        self.assertEqual(plan["eleven_app_contract_check"]["summary"]["passed"], 11)
        self.assertFalse(plan["raw_secret_stored"])
        self.assertIn("plan_fingerprint", plan)

    def test_gateway_algoquest_contracts_cli_json(self) -> None:
        code, output = self.capture(["--json", "gateway", "algoquest-contracts"])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["schema"], "securedme.education.algoquest-companion-plan.v1")
        self.assertTrue(payload["success"], payload)

    def test_gateway_algoquest_three_app_cli_json(self) -> None:
        code, output = self.capture(["--json", "gateway", "algoquest-three-app-test", "--score", "93"])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["schema"], "securedme.education.algoquest-three-app-test.v1")
        self.assertEqual(payload["apps"], ["visual-algorithm", "algoquest", "vot-guardian"])
        self.assertTrue(payload["success"], payload)

    def test_gateway_algoquest_11_app_check_cli_json(self) -> None:
        code, output = self.capture(["--json", "gateway", "algoquest-11-app-check"])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["schema"], "securedme.education.algoquest-11-app-contract-check.v1")
        self.assertEqual(payload["app_count"], 11)
        self.assertEqual(payload["summary"]["passed"], 11)
        self.assertTrue(payload["success"], payload)

    def test_direct_validators_accept_valid_payloads(self) -> None:
        install = build_gateway_install_sequence("algorithm-builder")
        session = build_session_role("teacher")
        student = build_student_learning_event(
            "visual-algorithm",
            "artifact:pointer",
            skill_area="algorithm_design",
            difficulty_band="grade5-sec2",
            score=93,
        )
        teacher = build_teacher_planning_event(
            "algoquest",
            classroom_scope="classroom-redacted",
            aggregate_need="extend_high_score_artifact",
            rubric_ref="rubric:algorithm_design",
            activity_ref="activity:algoquest",
        )
        metric = build_metrics_envelope("install", "gateway", "offer_shown", metric_store="install")
        qbit = build_qbit_intervention("teacher", trigger_reason="planning_gap", suggested_tool="algoquest")

        self.assertEqual(validate_gateway_install_sequence(install), [])
        self.assertEqual(validate_session_role(session), [])
        self.assertEqual(validate_student_learning_event(student), [])
        self.assertEqual(validate_teacher_planning_event(teacher), [])
        self.assertEqual(validate_metrics_envelope(metric), [])
        self.assertEqual(validate_qbit_intervention(qbit), [])


if __name__ == "__main__":
    unittest.main()
