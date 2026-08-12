import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from fnpqnn_gateway_mvp.auth0_gateway import (
    AUTH_TRANSACTION_COOKIE, Auth0Client, Auth0Config, IdentityApplication, SESSION_COOKIE,
)
from fnpqnn_gateway_mvp.identity_store import IdentityStore


class FakeAuth0Client:
    def __init__(self, config):
        self.config = config
        self.available = True

    def ready(self):
        return self.available and self.config.configured()

    def authorization_url(self, *, state, nonce, code_verifier):
        return "https://tenant.auth0.com/authorize?" + "&".join((f"state={state}", f"nonce={nonce}"))

    def exchange(self, *, code, code_verifier, nonce, organization_id):
        if code != "valid-code":
            raise ValueError("Auth0 ID token validation failed")
        return {
            "issuer": "https://tenant.auth0.com/",
            "subject": "auth0|synthetic-professor",
            "organization_id": organization_id,
            "auth_time": 1_788_000_000,
        }

    def logout_url(self):
        return "https://tenant.auth0.com/v2/logout"


class Auth0GatewayTests(unittest.TestCase):
    def setUp(self):
        self.store = IdentityStore(sqlite3.connect(":memory:"))
        self.config = Auth0Config(
            issuer="https://tenant.auth0.com",
            client_id="client-1",
            client_secret="test-only-secret",
            audience="https://gateway.securedme.ca/api",
            callback_url="https://gateway-dev.securedme.ca/auth/callback",
            logout_return_url="https://gateway-dev.securedme.ca/",
            organization_id="org_synthetic",
            allowed_return_urls=("https://algoquest-dev.securedme.ca/", "https://synthia-dev.securedme.ca/"),
            allowed_origins=("https://algoquest-dev.securedme.ca", "https://synthia-dev.securedme.ca"),
        )
        self.client = FakeAuth0Client(self.config)
        self.app = IdentityApplication(self.store, self.client, self.config)

    def call(self, method, path, *, query="", headers=None):
        env = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(b""),
        }
        env.update(headers or {})
        captured = {}
        def start(status, response_headers):
            captured.update(status=status, headers=response_headers)
        raw = b"".join(self.app(env, start))
        header_map = dict(captured["headers"])
        cookies = [value for key, value in captured["headers"] if key.lower() == "set-cookie"]
        if cookies:
            header_map["Set-Cookie"] = "\n".join(cookies)
        return captured["status"], header_map, json.loads(raw) if raw else {}

    def login_and_callback(self):
        status, headers, _ = self.call(
            "GET", "/auth/login", query="return_to=https%3A%2F%2Falgoquest-dev.securedme.ca%2F"
        )
        self.assertEqual(status, "302 Found")
        state = parse_qs(urlparse(headers["Location"]).query)["state"][0]
        transaction_cookie = next(
            value.split(";", 1)[0] for value in headers["Set-Cookie"].splitlines()
            if value.startswith(AUTH_TRANSACTION_COOKIE + "=")
        )
        status, headers, _ = self.call(
            "GET", "/auth/callback", query=f"state={state}&code=valid-code",
            headers={"HTTP_COOKIE": transaction_cookie},
        )
        self.assertEqual(status, "302 Found")
        self.assertEqual(headers["Location"], "https://algoquest-dev.securedme.ca/")
        return next(
            value.split(";", 1)[0] for value in headers["Set-Cookie"].splitlines()
            if value.startswith(SESSION_COOKIE + "=")
        )

    def test_login_rejects_open_redirect(self):
        status, _, payload = self.call(
            "GET", "/auth/login", query="return_to=https%3A%2F%2Fevil.example%2F"
        )
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(payload["error"], "return_to is not registered")

    def test_state_is_one_time(self):
        _, headers, _ = self.call(
            "GET", "/auth/login", query="return_to=https%3A%2F%2Falgoquest-dev.securedme.ca%2F"
        )
        state = parse_qs(urlparse(headers["Location"]).query)["state"][0]
        transaction_cookie = headers["Set-Cookie"].split(";", 1)[0]
        request_headers = {"HTTP_COOKIE": transaction_cookie}
        self.assertEqual(self.call(
            "GET", "/auth/callback", query=f"state={state}&code=valid-code", headers=request_headers
        )[0], "302 Found")
        status, _, payload = self.call(
            "GET", "/auth/callback", query=f"state={state}&code=valid-code", headers=request_headers
        )
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("already used", payload["error"])

    def test_callback_requires_the_browser_that_started_login(self):
        _, headers, _ = self.call(
            "GET", "/auth/login", query="return_to=https%3A%2F%2Falgoquest-dev.securedme.ca%2F"
        )
        state = parse_qs(urlparse(headers["Location"]).query)["state"][0]
        status, _, payload = self.call("GET", "/auth/callback", query=f"state={state}&code=valid-code")
        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(payload["error"], "authorization transaction browser binding failed")

    def test_authenticated_session_is_minimal_and_unassigned_by_default(self):
        cookie = self.login_and_callback()
        status, headers, session = self.call(
            "GET", "/api/v1/session",
            headers={"HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca"},
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://algoquest-dev.securedme.ca")
        self.assertEqual(session["schema"], "securedme.education.session.v2")
        self.assertEqual(session["role"], "unassigned")
        self.assertEqual(session["authorization_basis"]["decision"], "deny")
        self.assertNotIn("email", session)
        self.assertNotIn("access_token", session)
        self.assertGreaterEqual(len(session["csrf_token"]), 32)

    def test_role_is_an_internal_assignment_not_an_auth0_claim(self):
        cookie = self.login_and_callback()
        identity = self.store.connection.execute("SELECT securedme_id FROM upstream_identities").fetchone()[0]
        authority = "authority_" + __import__("hashlib").sha256(b"org_synthetic").hexdigest()[:20]
        self.store.assign_role(securedme_id=identity, authority_ref=authority, role="teacher",
                               age_band="adult-or-staff", consent_scope="suite", allowed_tools=["algoquest", "synthia"],
                               assigned_class_refs=["sci10-a"])
        # New authentication is required to project a changed assignment into a session.
        cookie = self.login_and_callback()
        _, _, session = self.call("GET", "/api/v1/session", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://synthia-dev.securedme.ca",
        })
        self.assertEqual(session["role"], "teacher")
        self.assertEqual(session["allowed_tools"], ["algoquest", "synthia"])
        self.assertEqual(session["assigned_class_refs"], ["sci10-a"])

    def test_legacy_adapter_refuses_unassigned_and_governance_roles(self):
        for role in ("unassigned", "privacy_admin", "school_admin"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                IdentityStore.to_session_v1({"role": role})

    def test_logout_requires_csrf_and_revokes_session(self):
        cookie = self.login_and_callback()
        _, _, session = self.call("GET", "/api/v1/session", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
        })
        status, _, _ = self.call("POST", "/auth/logout", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
        })
        self.assertEqual(status, "403 Forbidden")
        status, headers, payload = self.call("POST", "/auth/logout", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
            "HTTP_X_CSRF_TOKEN": session["csrf_token"],
        })
        self.assertEqual(status, "200 OK")
        self.assertTrue(payload["local_session_ended"])
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.call("GET", "/api/v1/session", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
        })[0], "401 Unauthorized")

    def test_identity_link_never_claims_success_without_provider_proof(self):
        cookie = self.login_and_callback()
        _, _, session = self.call("GET", "/api/v1/session", headers={
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
        })
        status, _, payload = self.call("POST", "/api/v1/identity-links", headers={
            "HTTP_COOKIE": cookie,
            "HTTP_ORIGIN": "https://algoquest-dev.securedme.ca",
            "HTTP_X_CSRF_TOKEN": session["csrf_token"],
        })
        self.assertEqual(status, "409 Conflict")
        self.assertFalse(payload["linked"])
        self.assertEqual(payload["error"], "verified_provider_link_required")

    def test_identity_database_backup_restores_assignments_and_sessions(self):
        cookie = self.login_and_callback()
        identity = self.store.connection.execute("SELECT securedme_id FROM upstream_identities").fetchone()[0]
        authority = "authority_" + __import__("hashlib").sha256(b"org_synthetic").hexdigest()[:20]
        self.store.assign_role(
            securedme_id=identity, authority_ref=authority, role="student_adult",
            age_band="16-24", consent_scope="suite", allowed_tools=["algoquest"],
            subject_ref="stu-restore",
        )
        self.assertIsNotNone(cookie)
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "identity-backup.sqlite3"
            backup_connection = sqlite3.connect(backup_path)
            self.store.connection.backup(backup_connection)
            backup_connection.close()
            restored = IdentityStore.from_path(str(backup_path))
            try:
                restored_assignment = restored.assignment_for(identity, authority)
                self.assertEqual(restored_assignment["role"], "student_adult")
                self.assertEqual(restored_assignment["subject_ref"], "stu-restore")
            finally:
                restored.connection.close()

    def test_cors_is_exact(self):
        status, _, payload = self.call("GET", "/api/v1/session", headers={"HTTP_ORIGIN": "https://evil.securedme.ca"})
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(payload["error"], "origin_not_allowed")

    def test_readiness_tracks_auth0(self):
        status, _, payload = self.call("GET", "/health/ready")
        self.assertEqual(status, "200 OK")
        self.assertTrue(payload["auth0_available"])
        self.assertGreaterEqual(payload["auth0_probe_latency_ms"], 0)
        self.client.available = False
        self.assertEqual(self.call("GET", "/health/ready")[0], "503 Service Unavailable")

    def test_login_rate_limit_is_ephemeral_and_returns_429(self):
        query = "return_to=https%3A%2F%2Falgoquest-dev.securedme.ca%2F"
        for _ in range(10):
            self.assertEqual(self.call("GET", "/auth/login", query=query)[0], "302 Found")
        status, headers, payload = self.call("GET", "/auth/login", query=query)
        self.assertEqual(status, "429 Too Many Requests")
        self.assertEqual(headers["Retry-After"], "60")
        self.assertEqual(payload["error"], "login_rate_limited")


class Auth0TokenValidationTests(unittest.TestCase):
    def setUp(self):
        self.config = Auth0Config(
            issuer="https://tenant.auth0.com", client_id="client-1", client_secret="test-only-secret",
            audience="https://gateway.securedme.ca/api",
            callback_url="https://gateway-dev.securedme.ca/auth/callback",
            logout_return_url="https://gateway-dev.securedme.ca/", organization_id="org_synthetic",
            allowed_return_urls=("https://algoquest-dev.securedme.ca/",),
            allowed_origins=("https://algoquest-dev.securedme.ca",),
        )
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = self.private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        self.jwk = JsonWebKey.import_key(public_pem, {"kid": "test-key", "use": "sig", "alg": "RS256"}).as_dict()

    def token(self, **overrides):
        claims = {
            "iss": self.config.issuer + "/", "aud": self.config.client_id,
            "sub": "auth0|synthetic", "exp": int(time.time()) + 300,
            "nonce": "expected-nonce", "org_id": self.config.organization_id,
            "amr": ["pwd"],
        }
        claims.update(overrides)
        if claims.get("amr") is None:
            claims.pop("amr", None)
        return jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, self.private_key).decode()

    def exchange(self, token):
        client = Auth0Client(self.config)
        client._discovery = {
            "issuer": self.config.issuer + "/", "jwks_uri": "https://tenant.auth0.com/.well-known/jwks.json",
            "token_endpoint": "https://tenant.auth0.com/oauth/token",
        }
        client._jwks, client._loaded_at = {"keys": [self.jwk]}, time.monotonic()
        response = io.BytesIO(json.dumps({"id_token": token}).encode())
        with patch("fnpqnn_gateway_mvp.auth0_gateway.request.urlopen", return_value=response):
            return client.exchange(code="one-time-code", code_verifier="verifier", nonce="expected-nonce",
                                   organization_id=self.config.organization_id)

    def test_rs256_jwks_and_required_claims(self):
        self.assertEqual(self.exchange(self.token())["subject"], "auth0|synthetic")
        invalid_claims = (
            {"aud": "wrong-client"}, {"nonce": "wrong-nonce"}, {"org_id": "org_wrong"},
            {"exp": int(time.time()) - 60}, {"amr": ["unsupported"]}, {"sub": "google-oauth2|synthetic"},
        )
        for overrides in invalid_claims:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.exchange(self.token(**overrides))

    def test_standard_auth0_id_token_without_amr_is_accepted(self):
        self.assertEqual(self.exchange(self.token(amr=None))["subject"], "auth0|synthetic")


if __name__ == "__main__":
    unittest.main()
