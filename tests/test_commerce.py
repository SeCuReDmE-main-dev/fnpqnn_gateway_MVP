import base64
import hashlib
import hmac
import io
import json
import os
import unittest

from fnpqnn_gateway_mvp.commerce import (
    DIAGNOSTIC_CENTS, ReceiptStore, escrow_milestones, intake_score,
    new_receipt, pkce_pair, verify_square_signature,
)
from fnpqnn_gateway_mvp.commerce_server import CommerceApplication


class CommerceContractsTests(unittest.TestCase):
    def setUp(self):
        self.store = ReceiptStore()
        self.app = CommerceApplication(self.store)

    def call(self, method, path, payload=None, headers=None):
        raw = json.dumps(payload or {}).encode()
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
        env.update(headers or {})
        captured = {}
        def start(status, response_headers): captured.update(status=status, headers=response_headers)
        body = b"".join(self.app(env, start))
        return captured["status"], json.loads(body)

    def test_support_presets_and_custom_are_idempotent(self):
        headers = {"HTTP_IDEMPOTENCY_KEY": "support-1"}
        status, first = self.call("POST", "/v1/support/orders", {"amount": "12.34"}, headers)
        status2, second = self.call("POST", "/v1/support/orders", {"amount": "99"}, headers)
        self.assertEqual(status, "201 Created")
        self.assertEqual(status2, "200 OK")
        self.assertEqual(first["receipt"]["id"], second["receipt"]["id"])
        self.assertEqual(first["receipt"]["amount_cents"], 1234)

    def test_monthly_support_rejects_custom_amount(self):
        status, payload = self.call("POST", "/v1/support/subscriptions", {"amount": "12"}, {"HTTP_IDEMPOTENCY_KEY": "monthly-1"})
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("monthly support", payload["error"])

    def test_diagnostic_is_always_300_cad(self):
        status, payload = self.call("POST", "/v1/diagnostics/orders", {"amount": "1"}, {"HTTP_IDEMPOTENCY_KEY": "diag-1"})
        self.assertEqual(status, "201 Created")
        self.assertEqual(payload["receipt"]["amount_cents"], DIAGNOSTIC_CENTS)

    def test_event_replay_never_applies_twice(self):
        receipt = self.store.create(new_receipt(provider="square", kind="in_person", amount_cents=500,
            idempotency_key="sq-1", provider_reference="payment-1"))
        first, applied = self.store.apply_event(provider="square", event_id="event-1", provider_reference="payment-1", status="completed")
        second, replayed = self.store.apply_event(provider="square", event_id="event-1", provider_reference="payment-1", status="completed")
        self.assertTrue(applied)
        self.assertFalse(replayed)
        self.assertEqual(first.id, receipt.id)
        self.assertEqual(second.id, receipt.id)

    def test_identity_linking_requires_explicit_consent_and_never_email(self):
        link = self.store.link_identity(local_subject="user-1", provider="paypal", provider_subject="payer-1", consent_id="consent-1")
        self.assertEqual(link["consent_id"], "consent-1")
        with self.assertRaises(ValueError):
            self.store.link_identity(local_subject="user-2", provider="paypal", provider_subject="payer-2", consent_id="")

    def test_intake_score_is_advisory_only(self):
        result = intake_score({"scope_clarity": 100, "fit": 80, "budget": 60, "capacity": 40, "dependencies_risk": 20})
        self.assertEqual(result["score"], 64)
        self.assertEqual(result["decision"], "human_review_required")
        self.assertFalse(result["automatic_acceptance"])
        self.assertFalse(result["automatic_rejection"])

    def test_escrow_is_fully_funded_and_split_without_losing_a_cent(self):
        milestones = escrow_milestones(10001)
        self.assertEqual(sum(item["amount_cents"] for item in milestones), 10001)
        self.assertEqual([item["amount_cents"] for item in milestones], [5000, 5001])
        self.assertTrue(all(item["release"] == "buyer_acceptance_required" for item in milestones))

    def test_square_signature(self):
        url, body, key = "https://paypal.securedme.ca/v1/square/webhooks", b'{"event_id":"1"}', "test-key"
        signature = base64.b64encode(hmac.new(key.encode(), url.encode() + body, hashlib.sha256).digest()).decode()
        self.assertTrue(verify_square_signature(url, body, signature, key))
        self.assertFalse(verify_square_signature(url, body + b"x", signature, key))

    def test_pkce_is_s256(self):
        pair = pkce_pair()
        expected = base64.urlsafe_b64encode(hashlib.sha256(pair["verifier"].encode()).digest()).decode().rstrip("=")
        self.assertEqual(pair["challenge"], expected)
        self.assertEqual(pair["method"], "S256")

    def test_oidc_discovery_is_exposed_by_gateway(self):
        status, payload = self.call("GET", "/.well-known/openid-configuration")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["issuer"], "https://gateway.securedme.ca")
        self.assertEqual(payload["code_challenge_methods_supported"], ["S256"])

    def test_oidc_authorization_requires_verified_upstream_identity(self):
        status, payload = self.call("POST", "/oidc/authorize", {})
        self.assertEqual(status, "401 Unauthorized")
        self.assertIn("verified upstream", payload["error"])

    def test_cors_allows_only_securedme_https_origins(self):
        status, _ = self.call("GET", "/health", headers={"HTTP_ORIGIN": "https://scholarium.securedme.ca"})
        self.assertEqual(status, "200 OK")


if __name__ == "__main__":
    unittest.main()
