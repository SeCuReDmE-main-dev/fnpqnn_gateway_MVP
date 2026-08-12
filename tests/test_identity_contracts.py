import json
from pathlib import Path
import unittest

from jsonschema import ValidationError

from fnpqnn_gateway_mvp.identity_contracts import validate_contract


class IdentityContractsTests(unittest.TestCase):
    def test_contracts_are_draft_2020_12_and_secret_minimized(self):
        root = Path(__file__).parents[1] / "contracts" / "identity"
        expected = {
            "securedme.identity.v1.schema.json",
            "securedme.education.session.v2.schema.json",
            "securedme.authorization_basis.v1.schema.json",
            "securedme.token_governor.handoff_envelope.v2.schema.json",
            "auth0_entitlement_snapshot.v1.schema.json",
            "auth0_usage_snapshot.v1.schema.json",
        }
        self.assertEqual({path.name for path in root.glob("*.json")}, expected)
        for path in root.glob("*.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            serialized = json.dumps(schema).lower()
            for forbidden in ("email", "password", "access_token", "refresh_token", "date_of_birth"):
                self.assertNotIn(forbidden, serialized)

    def test_handoff_preserves_fractal_hierarchy(self):
        path = Path(__file__).parents[1] / "contracts" / "identity" / "securedme.token_governor.handoff_envelope.v2.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["preserve_fields"]["const"],
                         ["I", "I_system^S", "D_f", "dF", "i_fractal"])

    def test_runtime_validator_accepts_usage_and_rejects_extra_identity_data(self):
        usage = {
            "schema": "auth0_usage_snapshot.v1",
            "synthetic_identity_count": 5,
            "monthly_active_identity_count": 3,
            "session_count": 7,
            "organization_count": 1,
            "events": {"login_success": 3},
            "contains_pii": False,
            "raw_secret_stored": False,
        }
        validate_contract("auth0_usage_snapshot.v1.schema.json", usage)
        with self.assertRaises(ValidationError):
            validate_contract("auth0_usage_snapshot.v1.schema.json", {**usage, "email": "blocked@example.test"})


if __name__ == "__main__":
    unittest.main()
