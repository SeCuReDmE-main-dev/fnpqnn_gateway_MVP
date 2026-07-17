import base64
import hashlib
import json
import sqlite3
import unittest

from fnpqnn_gateway_mvp.identity_broker import IdentityBroker, canonical_clients


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


class IdentityBrokerTests(unittest.TestCase):
    def setUp(self):
        self.broker = IdentityBroker(sqlite3.connect(":memory:"))
        self.client = canonical_clients()["scholarium"]
        self.verifier = "v" * 64
        self.challenge = b64(hashlib.sha256(self.verifier.encode()).digest())

    def test_all_twelve_clients_are_registered(self):
        self.assertEqual(len(canonical_clients()), 12)
        self.assertTrue(all(client.redirect_uri.startswith("https://") for client in canonical_clients().values()))

    def test_pkce_code_is_one_time_and_client_bound(self):
        code = self.broker.authorize(client_id=self.client.client_id, redirect_uri=self.client.redirect_uri,
            local_subject="local-user-1", provider="paypal", code_challenge=self.challenge, nonce="n-1")
        tokens = self.broker.exchange(code=code, client_id=self.client.client_id,
            redirect_uri=self.client.redirect_uri, code_verifier=self.verifier)
        self.assertEqual(tokens["token_type"], "Bearer")
        claims = json.loads(base64.urlsafe_b64decode(tokens["id_token"].split(".")[1] + "=="))
        self.assertEqual(claims["sub"], "local-user-1")
        self.assertEqual(claims["amr"], ["paypal"])
        with self.assertRaisesRegex(ValueError, "already used"):
            self.broker.exchange(code=code, client_id=self.client.client_id,
                redirect_uri=self.client.redirect_uri, code_verifier=self.verifier)

    def test_redirect_uri_is_exact(self):
        with self.assertRaisesRegex(ValueError, "unregistered"):
            self.broker.authorize(client_id=self.client.client_id, redirect_uri="https://evil.example/callback",
                local_subject="user", provider="github", code_challenge=self.challenge)

    def test_chatgpt_context_fails_closed_without_attestation(self):
        with self.assertRaisesRegex(ValueError, "attestation"):
            self.broker.authorize(client_id=self.client.client_id, redirect_uri=self.client.redirect_uri,
                local_subject="user", provider="chatgpt_context", code_challenge=self.challenge)

    def test_public_jwks_contains_no_private_material(self):
        jwk = self.broker.jwks()["keys"][0]
        self.assertEqual(jwk["alg"], "ES256")
        self.assertNotIn("d", jwk)


if __name__ == "__main__":
    unittest.main()

