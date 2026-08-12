"""Secret-minimized persistence for SecuredMe upstream identity sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import secrets
import sqlite3
from typing import Any


SESSION_SCHEMA = "securedme.education.session.v2"
IDENTITY_SCHEMA = "securedme.identity.v1"
AUTHORIZATION_BASIS_SCHEMA = "securedme.authorization_basis.v1"
SESSION_ROLES = {
    "student_minor", "student_adult", "teacher", "privacy_admin", "school_admin", "unassigned",
}
ROLE_SURFACES = {
    "student_minor": "student",
    "student_adult": "student",
    "teacher": "teacher",
    "privacy_admin": "governance",
    "school_admin": "governance",
    "unassigned": "unauthorized",
}
ROLE_PURPOSES = {
    "student_minor": "learning",
    "student_adult": "learning",
    "teacher": "teaching",
    "privacy_admin": "privacy_governance",
    "school_admin": "school_governance",
    "unassigned": "unassigned",
}


def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).replace(microsecond=0).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _identifier(prefix: str, bytes_count: int = 24) -> str:
    return f"{prefix}_{secrets.token_urlsafe(bytes_count)}"


@dataclass(frozen=True)
class AuthTransaction:
    state: str
    nonce: str
    code_verifier: str
    browser_binding: str
    return_to: str
    organization: str


class IdentityStore:
    """Persist identities and sessions without provider tokens or direct identifiers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS upstream_identities (
              securedme_id TEXT PRIMARY KEY,
              issuer TEXT NOT NULL,
              provider_subject TEXT NOT NULL,
              identity_ref TEXT NOT NULL UNIQUE,
              created_at INTEGER NOT NULL,
              UNIQUE(issuer, provider_subject)
            );
            CREATE TABLE IF NOT EXISTS authority_assignments (
              assignment_ref TEXT PRIMARY KEY,
              securedme_id TEXT NOT NULL,
              authority_ref TEXT NOT NULL,
              role TEXT NOT NULL,
              age_band TEXT NOT NULL,
              consent_scope TEXT NOT NULL,
              allowed_tools TEXT NOT NULL,
              subject_ref TEXT NOT NULL DEFAULT '',
              assigned_class_refs TEXT NOT NULL DEFAULT '[]',
              active INTEGER NOT NULL DEFAULT 1,
              created_at INTEGER NOT NULL,
              FOREIGN KEY(securedme_id) REFERENCES upstream_identities(securedme_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS authority_assignments_active
              ON authority_assignments(securedme_id, authority_ref) WHERE active = 1;
            CREATE TABLE IF NOT EXISTS auth_transactions (
              state_hash TEXT PRIMARY KEY,
              nonce TEXT NOT NULL,
              code_verifier TEXT NOT NULL,
              browser_binding_hash TEXT NOT NULL DEFAULT '',
              return_to TEXT NOT NULL,
              organization TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              consumed_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS gateway_sessions (
              session_hash TEXT PRIMARY KEY,
              securedme_id TEXT NOT NULL,
              authority_ref TEXT NOT NULL,
              assignment_ref TEXT NOT NULL,
              role TEXT NOT NULL,
              age_band TEXT NOT NULL,
              consent_scope TEXT NOT NULL,
              allowed_tools TEXT NOT NULL,
              subject_ref TEXT NOT NULL DEFAULT '',
              assigned_class_refs TEXT NOT NULL DEFAULT '[]',
              csrf_hash TEXT NOT NULL,
              auth_time INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              revoked_at INTEGER,
              FOREIGN KEY(securedme_id) REFERENCES upstream_identities(securedme_id)
            );
            CREATE TABLE IF NOT EXISTS auth_metrics (
              event TEXT PRIMARY KEY,
              count INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            """
        )
        self._ensure_column("authority_assignments", "subject_ref", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("authority_assignments", "assigned_class_refs", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("gateway_sessions", "subject_ref", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("gateway_sessions", "assigned_class_refs", "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column("auth_transactions", "browser_binding_hash", "TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def _ensure_column(self, table: str, column: str, declaration: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    @classmethod
    def from_path(cls, path: str) -> "IdentityStore":
        return cls(sqlite3.connect(path))

    def metric(self, event: str) -> None:
        if event not in {
            "login_attempt", "login_success", "login_failure", "session_expired",
            "unauthorized", "forbidden", "rate_limited", "logout",
        }:
            raise ValueError("unsupported auth metric")
        now = _now_epoch()
        self.connection.execute(
            "INSERT INTO auth_metrics(event, count, updated_at) VALUES (?, 1, ?) "
            "ON CONFLICT(event) DO UPDATE SET count = count + 1, updated_at = excluded.updated_at",
            (event, now),
        )
        self.connection.commit()

    def usage_snapshot(self) -> dict[str, Any]:
        rows = self.connection.execute("SELECT event, count FROM auth_metrics ORDER BY event").fetchall()
        organization_count = self.connection.execute(
            "SELECT COUNT(DISTINCT authority_ref) FROM authority_assignments WHERE active = 1"
        ).fetchone()[0]
        identity_count = self.connection.execute("SELECT COUNT(*) FROM upstream_identities").fetchone()[0]
        monthly_active = self.connection.execute(
            "SELECT COUNT(DISTINCT securedme_id) FROM gateway_sessions WHERE auth_time >= ?",
            (_now_epoch() - 30 * 24 * 60 * 60,),
        ).fetchone()[0]
        session_count = self.connection.execute("SELECT COUNT(*) FROM gateway_sessions").fetchone()[0]
        return {
            "schema": "auth0_usage_snapshot.v1",
            "synthetic_identity_count": identity_count,
            "monthly_active_identity_count": monthly_active,
            "session_count": session_count,
            "organization_count": organization_count,
            "events": {row["event"]: row["count"] for row in rows},
            "contains_pii": False,
            "raw_secret_stored": False,
        }

    def create_transaction(self, *, return_to: str, organization: str, ttl_seconds: int = 300) -> AuthTransaction:
        state = secrets.token_urlsafe(32)
        transaction = AuthTransaction(
            state=state,
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            browser_binding=secrets.token_urlsafe(32),
            return_to=return_to,
            organization=organization,
        )
        self.connection.execute(
            "INSERT INTO auth_transactions "
            "(state_hash, nonce, code_verifier, browser_binding_hash, return_to, organization, expires_at, consumed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (_hash(state), transaction.nonce, transaction.code_verifier, _hash(transaction.browser_binding),
             return_to, organization,
             _now_epoch() + min(max(ttl_seconds, 60), 600)),
        )
        self.connection.commit()
        return transaction

    def consume_transaction(self, state: str, browser_binding: str) -> AuthTransaction:
        state_hash = _hash(state)
        row = self.connection.execute(
            "SELECT * FROM auth_transactions WHERE state_hash = ?", (state_hash,)
        ).fetchone()
        now = _now_epoch()
        if row is None or row["consumed_at"] is not None or row["expires_at"] < now:
            raise ValueError("authorization transaction is invalid, expired, or already used")
        if not browser_binding or not secrets.compare_digest(row["browser_binding_hash"], _hash(browser_binding)):
            raise ValueError("authorization transaction browser binding failed")
        self.connection.execute(
            "UPDATE auth_transactions SET consumed_at = ? WHERE state_hash = ?", (now, state_hash)
        )
        self.connection.commit()
        return AuthTransaction(
            state, row["nonce"], row["code_verifier"], browser_binding, row["return_to"], row["organization"]
        )

    def resolve_identity(self, *, issuer: str, provider_subject: str) -> dict[str, str]:
        if not issuer.startswith("https://") or not provider_subject.strip():
            raise ValueError("verified issuer and subject are required")
        row = self.connection.execute(
            "SELECT * FROM upstream_identities WHERE issuer = ? AND provider_subject = ?",
            (issuer, provider_subject),
        ).fetchone()
        if row is None:
            securedme_id = _identifier("sid")
            identity_ref = "idref_" + hashlib.sha256(f"{issuer}\x00{provider_subject}".encode()).hexdigest()[:32]
            self.connection.execute(
                "INSERT INTO upstream_identities VALUES (?, ?, ?, ?, ?)",
                (securedme_id, issuer, provider_subject, identity_ref, _now_epoch()),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM upstream_identities WHERE securedme_id = ?", (securedme_id,)
            ).fetchone()
        return {"securedme_id": row["securedme_id"], "identity_ref": row["identity_ref"]}

    def assign_role(self, *, securedme_id: str, authority_ref: str, role: str, age_band: str,
                    consent_scope: str, allowed_tools: list[str], subject_ref: str = "",
                    assigned_class_refs: list[str] | None = None) -> dict[str, Any]:
        if role not in SESSION_ROLES - {"unassigned"}:
            raise ValueError("unsupported SecuredMe role")
        if not authority_ref.startswith("authority_"):
            raise ValueError("authority_ref must be pseudonymous")
        if consent_scope not in {"none", "tool", "suite"}:
            raise ValueError("unsupported consent scope")
        tools = sorted(set(allowed_tools))
        classes = sorted(set(assigned_class_refs or []))
        if not tools or len(tools) > 12 or any(not tool.replace("-", "").isalnum() for tool in tools):
            raise ValueError("allowed_tools must contain registered slugs")
        if role in {"student_minor", "student_adult"} and not subject_ref:
            raise ValueError("student assignments require a pseudonymous subject_ref")
        if role == "teacher" and not classes:
            raise ValueError("teacher assignments require at least one pseudonymous class reference")
        if self.connection.execute(
            "SELECT 1 FROM upstream_identities WHERE securedme_id = ?", (securedme_id,)
        ).fetchone() is None:
            raise ValueError("unknown SecuredMe identity")
        self.connection.execute(
            "UPDATE authority_assignments SET active = 0 WHERE securedme_id = ? AND authority_ref = ?",
            (securedme_id, authority_ref),
        )
        assignment_ref = _identifier("assignment", 16)
        self.connection.execute(
            "INSERT INTO authority_assignments "
            "(assignment_ref, securedme_id, authority_ref, role, age_band, consent_scope, allowed_tools, "
            "subject_ref, assigned_class_refs, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (assignment_ref, securedme_id, authority_ref, role, age_band[:40], consent_scope,
             json.dumps(tools, separators=(",", ":")), subject_ref[:100],
             json.dumps(classes, separators=(",", ":")), _now_epoch()),
        )
        self.connection.commit()
        return {"assignment_ref": assignment_ref, "securedme_id": securedme_id, "authority_ref": authority_ref,
                "role": role, "allowed_tools": tools, "raw_secret_stored": False}

    def assignment_for(self, securedme_id: str, authority_ref: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM authority_assignments WHERE securedme_id = ? AND authority_ref = ? AND active = 1",
            (securedme_id, authority_ref),
        ).fetchone()
        if row is None:
            return {
                "assignment_ref": "assignment_unassigned",
                "authority_ref": authority_ref,
                "role": "unassigned",
                "age_band": "unassigned",
                "consent_scope": "none",
                "allowed_tools": [], "subject_ref": "", "assigned_class_refs": [],
            }
        return {**dict(row), "allowed_tools": json.loads(row["allowed_tools"]),
                "assigned_class_refs": json.loads(row["assigned_class_refs"])}

    def create_session(self, *, securedme_id: str, authority_ref: str, auth_time: int,
                       ttl_seconds: int = 28_800) -> tuple[str, str, dict[str, Any]]:
        identity = self.connection.execute(
            "SELECT identity_ref FROM upstream_identities WHERE securedme_id = ?", (securedme_id,)
        ).fetchone()
        if identity is None:
            raise ValueError("unknown SecuredMe identity")
        assignment = self.assignment_for(securedme_id, authority_ref)
        session_token = _identifier("session")
        csrf_token = secrets.token_urlsafe(32)
        expires_at = _now_epoch() + min(max(ttl_seconds, 300), 28_800)
        self.connection.execute(
            "INSERT INTO gateway_sessions "
            "(session_hash, securedme_id, authority_ref, assignment_ref, role, age_band, consent_scope, "
            "allowed_tools, subject_ref, assigned_class_refs, csrf_hash, auth_time, expires_at, revoked_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (_hash(session_token), securedme_id, authority_ref, assignment["assignment_ref"], assignment["role"],
             assignment["age_band"], assignment["consent_scope"], json.dumps(assignment["allowed_tools"]),
             assignment.get("subject_ref", ""), json.dumps(assignment.get("assigned_class_refs", [])),
             _hash(csrf_token), auth_time, expires_at),
        )
        self.connection.commit()
        return session_token, csrf_token, self._session_payload(
            session_token, csrf_token, identity["identity_ref"], assignment, auth_time, expires_at
        )

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        if not session_token:
            return None
        row = self.connection.execute(
            "SELECT s.*, i.identity_ref FROM gateway_sessions s JOIN upstream_identities i "
            "ON i.securedme_id = s.securedme_id WHERE s.session_hash = ?", (_hash(session_token),)
        ).fetchone()
        if row is None or row["revoked_at"] is not None:
            return None
        if row["expires_at"] <= _now_epoch():
            self.metric("session_expired")
            return None
        assignment = {
            "assignment_ref": row["assignment_ref"], "authority_ref": row["authority_ref"],
            "role": row["role"], "age_band": row["age_band"], "consent_scope": row["consent_scope"],
            "allowed_tools": json.loads(row["allowed_tools"]),
            "subject_ref": row["subject_ref"],
            "assigned_class_refs": json.loads(row["assigned_class_refs"]),
        }
        return self._session_payload(
            session_token, "", row["identity_ref"], assignment, row["auth_time"], row["expires_at"]
        )

    def get_session_identity(self, session_token: str) -> dict[str, Any] | None:
        session = self.get_session(session_token)
        if session is None:
            return None
        row = self.connection.execute(
            "SELECT securedme_id FROM gateway_sessions WHERE session_hash = ?", (_hash(session_token),)
        ).fetchone()
        return {**session, "_securedme_id": row["securedme_id"]}

    def validate_csrf(self, session_token: str, csrf_token: str) -> bool:
        row = self.connection.execute(
            "SELECT csrf_hash FROM gateway_sessions WHERE session_hash = ? AND revoked_at IS NULL",
            (_hash(session_token),),
        ).fetchone()
        return bool(row and csrf_token and secrets.compare_digest(row["csrf_hash"], _hash(csrf_token)))

    def revoke_session(self, session_token: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE gateway_sessions SET revoked_at = ? WHERE session_hash = ? AND revoked_at IS NULL",
            (_now_epoch(), _hash(session_token)),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def _session_payload(self, session_token: str, csrf_token: str, identity_ref: str,
                         assignment: dict[str, Any], auth_time: int, expires_at: int) -> dict[str, Any]:
        role = assignment["role"]
        payload = {
            "schema": SESSION_SCHEMA,
            "session_id": session_token.split("_", 1)[0] + "_" + _hash(session_token)[:24],
            "identity_ref": identity_ref,
            "role": role,
            "age_band": assignment["age_band"],
            "surface": ROLE_SURFACES[role],
            "authority_ref": assignment["authority_ref"],
            "subject_ref": assignment.get("subject_ref", ""),
            "assigned_class_refs": assignment.get("assigned_class_refs", []),
            "consent_scope": assignment["consent_scope"],
            "allowed_tools": assignment["allowed_tools"],
            "authorization_basis": {
                "schema": AUTHORIZATION_BASIS_SCHEMA,
                "assignment_ref": assignment["assignment_ref"],
                "authority_ref": assignment["authority_ref"],
                "subject_ref": assignment.get("subject_ref", ""),
                "assigned_class_refs": assignment.get("assigned_class_refs", []),
                "purpose": ROLE_PURPOSES[role],
                "decision": "deny" if role == "unassigned" else "allow",
                "human_authority_required": True,
            },
            "auth_time": _iso(auth_time),
            "expires_at": _iso(expires_at),
            "csrf_token": csrf_token,
            "contract_version": "v2",
            "raw_secret_stored": False,
        }
        return payload

    @staticmethod
    def to_session_v1(session: dict[str, Any]) -> dict[str, Any]:
        role = session["role"]
        if role not in {"student_minor", "student_adult", "teacher"}:
            raise ValueError("session role cannot be represented by the v1 adapter")
        return {
            "schema": "securedme.education.session-role.v1",
            "session_id": session["session_id"],
            "fingerprint_ref": session["identity_ref"],
            "role": role,
            "age_band": session["age_band"],
            "surface": "teacher" if role == "teacher" else "student",
            "consent_scope": session["consent_scope"],
            "allowed_tools": session["allowed_tools"],
            "expires_at": session["expires_at"],
            "contract_version": "v1",
            "raw_secret_stored": False,
        }
