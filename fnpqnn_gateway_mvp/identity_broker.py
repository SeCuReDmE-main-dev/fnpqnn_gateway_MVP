"""OIDC/PKCE contracts for the twelve SecuredMe Education applications."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import sqlite3
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


ISSUER = "https://gateway.securedme.ca"
SUPPORTED_PROVIDERS = ("google", "github", "paypal", "chatgpt_context")
CLIENT_DOMAINS = {
    "synthia": "synthia.securedme.ca",
    "fnpqnn": "fnpqnn.securedme.ca",
    "gateway": "gateway.securedme.ca",
    "ffed-qlc": "ffed-qlc.securedme.ca",
    "scholarium": "scholarium.securedme.ca",
    "quanthor": "quanthor.securedme.ca",
    "visual-algorithm": "visual-algorithm.securedme.ca",
    "algorithm-builder": "algorithm-builder.securedme.ca",
    "algoquest": "algoquest.securedme.ca",
    "vot-guardian": "vot-guardian.securedme.ca",
    "market-guardian": "market-guardian.securedme.ca",
    "tesla-workbench": "tesla-workbench.securedme.ca",
}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Client:
    client_id: str
    redirect_uri: str


def canonical_clients() -> dict[str, Client]:
    return {slug: Client(f"securedme-{slug}", f"https://{domain}/auth/callback")
            for slug, domain in CLIENT_DOMAINS.items()}


class IdentityBroker:
    """One-time authorization-code issuer for upstream-verified identities."""

    def __init__(self, connection: sqlite3.Connection, private_key: ec.EllipticCurvePrivateKey | None = None) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.private_key = private_key or ec.generate_private_key(ec.SECP256R1())
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS oidc_codes (
              code_hash TEXT PRIMARY KEY,
              client_id TEXT NOT NULL,
              redirect_uri TEXT NOT NULL,
              local_subject TEXT NOT NULL,
              provider TEXT NOT NULL,
              code_challenge TEXT NOT NULL,
              nonce TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              consumed_at INTEGER
            );
            """
        )

    @classmethod
    def from_pem(cls, connection: sqlite3.Connection, pem: bytes) -> "IdentityBroker":
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise ValueError("OIDC signing key must be an EC private key")
        return cls(connection, key)

    def discovery(self) -> dict[str, Any]:
        return {
            "issuer": ISSUER,
            "authorization_endpoint": ISSUER + "/oidc/authorize",
            "token_endpoint": ISSUER + "/oidc/token",
            "jwks_uri": ISSUER + "/oidc/jwks.json",
            "end_session_endpoint": ISSUER + "/oidc/logout",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["ES256"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["openid", "profile", "email"],
        }

    def jwks(self) -> dict[str, Any]:
        numbers = self.private_key.public_key().public_numbers()
        return {"keys": [{"kty": "EC", "crv": "P-256", "use": "sig", "alg": "ES256",
            "kid": "securedme-gateway-1", "x": _b64(numbers.x.to_bytes(32, "big")),
            "y": _b64(numbers.y.to_bytes(32, "big"))}]}

    def authorize(self, *, client_id: str, redirect_uri: str, local_subject: str,
                  provider: str, code_challenge: str, nonce: str = "",
                  chatgpt_context_attested: bool = False) -> str:
        client = next((item for item in canonical_clients().values() if item.client_id == client_id), None)
        if client is None or redirect_uri != client.redirect_uri:
            raise ValueError("unregistered OIDC client or redirect URI")
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported upstream identity provider")
        if provider == "chatgpt_context" and not chatgpt_context_attested:
            raise ValueError("ChatGPT context identity requires host attestation")
        if not local_subject.strip() or len(code_challenge) < 43:
            raise ValueError("verified subject and PKCE S256 challenge are required")
        code = secrets.token_urlsafe(40)
        self.connection.execute(
            "INSERT INTO oidc_codes VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (hashlib.sha256(code.encode()).hexdigest(), client_id, redirect_uri, local_subject,
             provider, code_challenge, nonce[:256], int((_now() + timedelta(minutes=5)).timestamp())),
        )
        self.connection.commit()
        return code

    def exchange(self, *, code: str, client_id: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        row = self.connection.execute("SELECT * FROM oidc_codes WHERE code_hash = ?", (code_hash,)).fetchone()
        now = int(_now().timestamp())
        if row is None or row["consumed_at"] is not None or row["expires_at"] < now:
            raise ValueError("authorization code is invalid, expired, or already used")
        if row["client_id"] != client_id or row["redirect_uri"] != redirect_uri:
            raise ValueError("authorization code client binding failed")
        challenge = _b64(hashlib.sha256(code_verifier.encode()).digest())
        if not secrets.compare_digest(challenge, row["code_challenge"]):
            raise ValueError("PKCE verification failed")
        self.connection.execute("UPDATE oidc_codes SET consumed_at = ? WHERE code_hash = ?", (now, code_hash))
        self.connection.commit()
        claims = {"iss": ISSUER, "aud": client_id, "sub": row["local_subject"], "iat": now,
                  "exp": now + 300, "auth_time": now, "amr": [row["provider"]]}
        if row["nonce"]:
            claims["nonce"] = row["nonce"]
        return {"access_token": self._jwt({**claims, "scope": "openid profile email"}),
                "id_token": self._jwt(claims), "token_type": "Bearer", "expires_in": 300,
                "scope": "openid profile email"}

    def _jwt(self, claims: dict[str, Any]) -> str:
        header = _b64(json.dumps({"alg": "ES256", "kid": "securedme-gateway-1", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
        signing_input = f"{header}.{payload}".encode()
        der = self.private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return f"{header}.{payload}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def generate_private_key_pem() -> bytes:
    return ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

