"""Auth0 upstream authentication boundary for the SecuredMe Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
import time
from typing import Any, Callable
from urllib import error, parse, request

from authlib.jose import JoseError, JsonWebKey, jwt

from .identity_contracts import validate_contract
from .identity_store import IdentityStore


JsonStart = Callable[[str, list[tuple[str, str]]], None]
SESSION_COOKIE = "__Host-securedme_session"
AUTH_TRANSACTION_COOKIE = "__Host-securedme_auth_tx"


class RateLimitError(Exception):
    """An ephemeral login throttle was exceeded."""


def _json_response(start_response: JsonStart, status: str, payload: dict[str, Any],
                   extra_headers: list[tuple[str, str]] | None = None) -> list[bytes]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("Pragma", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
    ]
    headers.extend(extra_headers or [])
    start_response(status, headers)
    return [body]


def _redirect(start_response: JsonStart, location: str, headers: list[tuple[str, str]] | None = None) -> list[bytes]:
    response_headers = [("Location", location), ("Content-Length", "0"), ("Cache-Control", "no-store")]
    response_headers.extend(headers or [])
    start_response("302 Found", response_headers)
    return [b""]


def _cookie(environ: dict[str, Any], name: str) -> str:
    for part in str(environ.get("HTTP_COOKIE", "")).split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key == name:
            return value
    return ""


def _query(environ: dict[str, Any]) -> dict[str, str]:
    return {key: values[-1] for key, values in parse.parse_qs(
        str(environ.get("QUERY_STRING", "")), keep_blank_values=True, max_num_fields=20
    ).items()}


def _pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


@dataclass(frozen=True)
class Auth0Config:
    issuer: str
    client_id: str
    client_secret: str
    audience: str
    callback_url: str
    logout_return_url: str
    organization_id: str
    allowed_return_urls: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    allowed_auth_methods: tuple[str, ...] = ("pwd", "mfa", "federated", "passkey")
    allowed_subject_prefixes: tuple[str, ...] = ("auth0",)

    @classmethod
    def from_env(cls) -> "Auth0Config":
        issuer = os.environ.get("AUTH0_ISSUER_BASE_URL", "").rstrip("/")
        return cls(
            issuer=issuer,
            client_id=os.environ.get("AUTH0_CLIENT_ID", ""),
            client_secret=os.environ.get("AUTH0_CLIENT_SECRET", ""),
            audience=os.environ.get("AUTH0_AUDIENCE", "https://gateway.securedme.ca/api"),
            callback_url=os.environ.get("AUTH0_CALLBACK_URL", "https://gateway-dev.securedme.ca/auth/callback"),
            logout_return_url=os.environ.get("AUTH0_LOGOUT_URL", "https://gateway-dev.securedme.ca/"),
            organization_id=os.environ.get("AUTH0_ORGANIZATION_ID", ""),
            allowed_return_urls=tuple(filter(None, (value.strip() for value in os.environ.get(
                "SECUREDME_AUTH_ALLOWED_RETURN_URLS",
                "https://algoquest-dev.securedme.ca/,https://synthia-dev.securedme.ca/",
            ).split(",")))),
            allowed_origins=tuple(filter(None, (value.strip() for value in os.environ.get(
                "SECUREDME_AUTH_ALLOWED_ORIGINS",
                "https://algoquest-dev.securedme.ca,https://synthia-dev.securedme.ca",
            ).split(",")))),
            allowed_auth_methods=tuple(filter(None, (value.strip() for value in os.environ.get(
                "AUTH0_ALLOWED_AMR", "pwd,mfa,federated,passkey"
            ).split(",")))),
            allowed_subject_prefixes=tuple(filter(None, (value.strip() for value in os.environ.get(
                "AUTH0_ALLOWED_SUBJECT_PREFIXES", "auth0"
            ).split(",")))),
        )

    def configured(self) -> bool:
        return bool(self.issuer and self.client_id and self.client_secret and self.organization_id)


class Auth0Client:
    """Minimal server-side OIDC client using Authlib for claim verification."""

    def __init__(self, config: Auth0Config, *, timeout: int = 10) -> None:
        self.config = config
        self.timeout = timeout
        self._discovery: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None
        self._loaded_at = 0.0

    def _load_metadata(self, *, force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
        if not force and self._discovery and self._jwks and time.monotonic() - self._loaded_at < 3600:
            return self._discovery, self._jwks
        with request.urlopen(self.config.issuer + "/.well-known/openid-configuration", timeout=self.timeout) as response:
            discovery = json.load(response)
        if discovery.get("issuer", "").rstrip("/") != self.config.issuer:
            raise ValueError("Auth0 discovery issuer mismatch")
        with request.urlopen(discovery["jwks_uri"], timeout=self.timeout) as response:
            jwks = json.load(response)
        self._discovery, self._jwks, self._loaded_at = discovery, jwks, time.monotonic()
        return discovery, jwks

    def ready(self) -> bool:
        if not self.config.configured():
            return False
        try:
            self._load_metadata(force=True)
            return True
        except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
            return False

    def authorization_url(self, *, state: str, nonce: str, code_verifier: str) -> str:
        discovery, _ = self._load_metadata()
        parameters = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.callback_url,
            "scope": "openid",
            "audience": self.config.audience,
            "organization": self.config.organization_id,
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        return discovery["authorization_endpoint"] + "?" + parse.urlencode(parameters)

    def exchange(self, *, code: str, code_verifier: str, nonce: str, organization_id: str) -> dict[str, Any]:
        discovery, jwks = self._load_metadata()
        form = parse.urlencode({
            "grant_type": "authorization_code", "client_id": self.config.client_id,
            "client_secret": self.config.client_secret, "code": code,
            "redirect_uri": self.config.callback_url, "code_verifier": code_verifier,
        }).encode()
        token_request = request.Request(
            discovery["token_endpoint"], data=form, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with request.urlopen(token_request, timeout=self.timeout) as response:
            tokens = json.load(response)
        token = str(tokens.get("id_token", ""))
        if not token:
            raise ValueError("Auth0 did not return an ID token")
        try:
            claims = jwt.decode(
                token,
                JsonWebKey.import_key_set(jwks),
                claims_options={
                    "iss": {"essential": True, "value": self.config.issuer + "/"},
                    "aud": {"essential": True, "value": self.config.client_id},
                    "exp": {"essential": True},
                    "sub": {"essential": True},
                    "nonce": {"essential": True, "value": nonce},
                    "org_id": {"essential": True, "value": organization_id},
                },
            )
            claims.validate(leeway=30)
        except JoseError as exc:
            raise ValueError("Auth0 ID token validation failed") from exc
        subject_prefix = str(claims["sub"]).partition("|")[0]
        if subject_prefix not in self.config.allowed_subject_prefixes:
            raise ValueError("Auth0 identity connection is not allowed")
        authentication_methods = claims.get("amr")
        if authentication_methods is not None and (
            not isinstance(authentication_methods, list) or
            not set(authentication_methods).intersection(self.config.allowed_auth_methods)
        ):
            raise ValueError("Auth0 authentication method is not allowed")
        return {
            "issuer": str(claims["iss"]),
            "subject": str(claims["sub"]),
            "organization_id": str(claims["org_id"]),
            "auth_time": int(claims.get("auth_time", datetime.now(timezone.utc).timestamp())),
        }

    def logout_url(self) -> str:
        discovery, _ = self._load_metadata()
        endpoint = discovery.get("end_session_endpoint") or self.config.issuer + "/v2/logout"
        return endpoint + "?" + parse.urlencode({
            "client_id": self.config.client_id, "returnTo": self.config.logout_return_url,
        })


class IdentityApplication:
    """WSGI route component for upstream login and internal Gateway sessions."""

    ROUTES = {
        "/auth/login", "/auth/callback", "/auth/logout", "/api/v1/session",
        "/api/v1/identity-links", "/v1/identity-links", "/api/v1/auth/usage",
        "/health/live", "/health/ready",
    }

    def __init__(self, store: IdentityStore, client: Auth0Client, config: Auth0Config) -> None:
        self.store, self.client, self.config = store, client, config
        self._login_attempts: dict[str, list[float]] = {}

    def handles(self, path: str) -> bool:
        return path in self.ROUTES

    def __call__(self, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        origin = str(environ.get("HTTP_ORIGIN", ""))
        if method == "OPTIONS":
            if origin not in self.config.allowed_origins:
                return _json_response(start_response, "403 Forbidden", {"error": "origin_not_allowed"})
            start_response("204 No Content", [
                ("Access-Control-Allow-Origin", origin), ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token"),
                ("Access-Control-Max-Age", "600"), ("Vary", "Origin"), ("Content-Length", "0"),
            ])
            return [b""]
        cors = []
        if origin:
            if origin not in self.config.allowed_origins:
                return _json_response(start_response, "403 Forbidden", {"error": "origin_not_allowed"})
            cors = [("Access-Control-Allow-Origin", origin), ("Access-Control-Allow-Credentials", "true"), ("Vary", "Origin")]
        try:
            if method == "GET" and path == "/health/live":
                return _json_response(start_response, "200 OK", {"status": "live", "service": "securedme-identity"}, cors)
            if method == "GET" and path == "/health/ready":
                started = time.perf_counter()
                ready = self.client.ready()
                return _json_response(start_response, "200 OK" if ready else "503 Service Unavailable",
                                      {"status": "ready" if ready else "not_ready",
                                       "auth0_configured": self.config.configured(),
                                       "auth0_available": ready,
                                       "auth0_probe_latency_ms": round((time.perf_counter() - started) * 1000, 2)}, cors)
            if method == "GET" and path == "/auth/login":
                return self._login(environ, start_response)
            if method == "GET" and path == "/auth/callback":
                return self._callback(environ, start_response)
            if method == "GET" and path == "/api/v1/session":
                return self._session(environ, start_response, cors)
            if method == "POST" and path == "/auth/logout":
                return self._logout(environ, start_response, cors)
            if method == "POST" and path in {"/api/v1/identity-links", "/v1/identity-links"}:
                return self._identity_link(environ, start_response, cors)
            if method == "GET" and path == "/api/v1/auth/usage":
                session = self._require_session(environ)
                if session["role"] not in {"privacy_admin", "school_admin"}:
                    self.store.metric("forbidden")
                    return _json_response(start_response, "403 Forbidden", {"error": "insufficient_role"}, cors)
                usage = self.store.usage_snapshot()
                validate_contract("auth0_usage_snapshot.v1.schema.json", usage)
                return _json_response(start_response, "200 OK", usage, cors)
            return _json_response(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"}, cors)
        except ValueError as exc:
            error_name = str(exc)
            if error_name == "csrf_validation_failed":
                self.store.metric("forbidden")
            elif path in {"/auth/login", "/auth/callback"}:
                self.store.metric("login_failure")
            else:
                self.store.metric("unauthorized")
            status = "401 Unauthorized" if error_name == "session_required" else (
                "403 Forbidden" if error_name == "csrf_validation_failed" else "400 Bad Request"
            )
            return _json_response(start_response, status, {"error": error_name}, cors)
        except RateLimitError:
            self.store.metric("rate_limited")
            return _json_response(start_response, "429 Too Many Requests", {"error": "login_rate_limited"},
                                  cors + [("Retry-After", "60")])
        except (error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
            self.store.metric("login_failure")
            return _json_response(start_response, "503 Service Unavailable", {"error": "identity_provider_unavailable"}, cors)

    def _login(self, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        self._enforce_login_rate_limit(str(environ.get("REMOTE_ADDR", "unknown")))
        if not self.config.configured():
            raise ValueError("Auth0 is not configured")
        return_to = _query(environ).get("return_to", "")
        if return_to not in self.config.allowed_return_urls:
            raise ValueError("return_to is not registered")
        self.store.metric("login_attempt")
        transaction = self.store.create_transaction(return_to=return_to, organization=self.config.organization_id)
        transaction_cookie = (
            f"{AUTH_TRANSACTION_COOKIE}={transaction.browser_binding}; Path=/; Secure; HttpOnly; "
            "SameSite=Lax; Max-Age=300"
        )
        return _redirect(start_response, self.client.authorization_url(
            state=transaction.state, nonce=transaction.nonce, code_verifier=transaction.code_verifier
        ), [("Set-Cookie", transaction_cookie)])

    def _enforce_login_rate_limit(self, client_key: str) -> None:
        now = time.monotonic()
        recent = [observed for observed in self._login_attempts.get(client_key, []) if now - observed < 60]
        if len(recent) >= 10:
            raise RateLimitError
        recent.append(now)
        self._login_attempts[client_key] = recent

    def _callback(self, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        query = _query(environ)
        if query.get("error"):
            raise ValueError("Auth0 authorization was denied")
        state, code = query.get("state", ""), query.get("code", "")
        if not state or not code:
            raise ValueError("authorization code and state are required")
        transaction = self.store.consume_transaction(state, _cookie(environ, AUTH_TRANSACTION_COOKIE))
        claims = self.client.exchange(code=code, code_verifier=transaction.code_verifier,
                                      nonce=transaction.nonce, organization_id=transaction.organization)
        identity = self.store.resolve_identity(issuer=claims["issuer"], provider_subject=claims["subject"])
        authority_ref = "authority_" + hashlib.sha256(claims["organization_id"].encode()).hexdigest()[:20]
        session_token, _, _ = self.store.create_session(
            securedme_id=identity["securedme_id"], authority_ref=authority_ref, auth_time=claims["auth_time"]
        )
        self.store.metric("login_success")
        set_cookie = f"{SESSION_COOKIE}={session_token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=28800"
        clear_transaction = f"{AUTH_TRANSACTION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
        return _redirect(start_response, transaction.return_to, [
            ("Set-Cookie", set_cookie), ("Set-Cookie", clear_transaction),
        ])

    def _session(self, environ: dict[str, Any], start_response: JsonStart,
                 cors: list[tuple[str, str]]) -> list[bytes]:
        token = _cookie(environ, SESSION_COOKIE)
        session = self.store.get_session(token)
        if session is None:
            self.store.metric("unauthorized")
            return _json_response(start_response, "401 Unauthorized", {"error": "session_required"}, cors)
        # The CSRF value is deliberately returned only over an authenticated, exact-origin request.
        # A hash cannot be used as the CSRF token, so rotate a fresh value into this session.
        csrf_token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        self.store.connection.execute(
            "UPDATE gateway_sessions SET csrf_hash = ? WHERE session_hash = ?",
            (hashlib.sha256(csrf_token.encode()).hexdigest(), hashlib.sha256(token.encode()).hexdigest()),
        )
        self.store.connection.commit()
        session["csrf_token"] = csrf_token
        validate_contract("securedme.education.session.v2.schema.json", session)
        return _json_response(start_response, "200 OK", session, cors)

    def _require_session(self, environ: dict[str, Any], *, csrf: bool = False) -> dict[str, Any]:
        token = _cookie(environ, SESSION_COOKIE)
        session = self.store.get_session_identity(token)
        if session is None:
            raise ValueError("session_required")
        if csrf and not self.store.validate_csrf(token, str(environ.get("HTTP_X_CSRF_TOKEN", ""))):
            raise ValueError("csrf_validation_failed")
        return session

    def verified_session(self, environ: dict[str, Any], *, csrf: bool = False) -> dict[str, Any]:
        """Return a server-internal session containing the non-public SecuredMe subject."""
        return self._require_session(environ, csrf=csrf)

    def _logout(self, environ: dict[str, Any], start_response: JsonStart,
                cors: list[tuple[str, str]]) -> list[bytes]:
        self._require_session(environ, csrf=True)
        token = _cookie(environ, SESSION_COOKIE)
        self.store.revoke_session(token)
        self.store.metric("logout")
        clear_cookie = f"{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
        try:
            auth0_logout_url = self.client.logout_url()
            auth0_logout_available = True
        except (error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
            auth0_logout_url = None
            auth0_logout_available = False
        payload = {"local_session_ended": True, "auth0_session_ended": False,
                   "upstream_provider_session_ended": False,
                   "auth0_logout_available": auth0_logout_available,
                   "auth0_logout_url": auth0_logout_url}
        return _json_response(start_response, "200 OK", payload, cors + [("Set-Cookie", clear_cookie)])

    def _identity_link(self, environ: dict[str, Any], start_response: JsonStart,
                       cors: list[tuple[str, str]]) -> list[bytes]:
        self._require_session(environ, csrf=True)
        return _json_response(start_response, "409 Conflict", {
            "error": "verified_provider_link_required",
            "linked": False,
            "email_auto_merge": False,
            "raw_secret_stored": False,
        }, cors)
