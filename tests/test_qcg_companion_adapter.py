from __future__ import annotations

import contextlib
import io
import json
import unittest

from fnpqnn_gateway_mvp.cli import main
from fnpqnn_gateway_mvp.qcg_companion_adapter import (
    QCG_VIEWS,
    build_qcg_companion_snapshot,
    navigate_qcg_companion,
)


SESSION_ID = "21ce8a13-35d2-4b31-9eb0-a81af9629c64"
CREATED_AT = "2026-09-02T10:00:00+00:00"


class QcgCompanionGatewayAdapterTests(unittest.TestCase):
    def test_builds_qcg_v2_snapshot_without_private_gateway_state(self) -> None:
        envelope = build_qcg_companion_snapshot(
            session_id=SESSION_ID,
            view="activity",
            gateway_state="ready",
            validated_contracts=4,
            evidence_exports=2,
            created_at=CREATED_AT,
        )

        snapshot = envelope["qcg_snapshot"]
        serialized = json.dumps(envelope, sort_keys=True).lower()
        self.assertEqual(envelope["schema"], "securedme.gateway.qcg-companion-adapter.v1")
        self.assertEqual(snapshot["schema_version"], "qcg-console-snapshot.v2")
        self.assertEqual(snapshot["surface"], "sidepanel")
        self.assertEqual(snapshot["session_id"], SESSION_ID)
        self.assertEqual(snapshot["effects"]["metadata_validations"], 4)
        self.assertEqual(envelope["navigation"]["available"], list(QCG_VIEWS))
        self.assertFalse(envelope["boundary"]["raw_gateway_payload_included"])
        self.assertFalse(envelope["boundary"]["credentials_included"])
        self.assertFalse(envelope["boundary"]["consent_created"])
        for forbidden in (".env", "api_key", "access_token", "openclaw", "provider response"):
            self.assertNotIn(forbidden, serialized)

    def test_navigation_rebuilds_view_and_preserves_session_and_counts(self) -> None:
        initial = build_qcg_companion_snapshot(
            session_id=SESSION_ID,
            validated_contracts=3,
            evidence_exports=1,
            created_at=CREATED_AT,
        )

        navigated = navigate_qcg_companion(initial, "receipts")

        self.assertEqual(navigated["selected_view"], "receipts")
        self.assertEqual(navigated["qcg_snapshot"]["session_id"], SESSION_ID)
        self.assertEqual(navigated["qcg_snapshot"]["effects"]["metadata_validations"], 3)
        self.assertEqual(navigated["qcg_snapshot"]["effects"]["evidence_exports"], 1)

    def test_rejects_unknown_view_invalid_uuid_and_unbounded_counter(self) -> None:
        with self.assertRaisesRegex(ValueError, "view must be one of"):
            build_qcg_companion_snapshot(session_id=SESSION_ID, view="admin")
        with self.assertRaisesRegex(ValueError, "session_id must be a UUID"):
            build_qcg_companion_snapshot(session_id="not-a-session")
        with self.assertRaisesRegex(ValueError, "validated_contracts"):
            build_qcg_companion_snapshot(session_id=SESSION_ID, validated_contracts=-1)
        with self.assertRaisesRegex(ValueError, "created_at"):
            build_qcg_companion_snapshot(session_id=SESSION_ID, created_at="not-a-timestamp")

    def test_cli_emits_bounded_snapshot(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(
                [
                    "--json",
                    "gateway",
                    "qcg-companion-snapshot",
                    "--session-id",
                    SESSION_ID,
                    "--view",
                    "sources",
                    "--validated-contracts",
                    "2",
                ]
            )

        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["selected_view"], "sources")
        self.assertEqual(payload["qcg_snapshot"]["effects"]["metadata_validations"], 2)


if __name__ == "__main__":
    unittest.main()
