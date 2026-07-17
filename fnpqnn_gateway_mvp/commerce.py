"""SecuredMe commerce and identity contracts.

The module is deliberately dependency-free and secret-blind. Provider secrets
are accepted only by the edge adapters that call PayPal or Square; the durable
ledger stores public provider references, hashes, and receipt state only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


PROVIDERS = ("paypal", "square", "interac", "escrow")
SUPPORT_PRESETS_CENTS = (500, 1000, 2500)
DIAGNOSTIC_CENTS = 30000
INTAKE_WEIGHTS = {
    "scope_clarity": 25,
    "fit": 20,
    "budget": 20,
    "capacity": 20,
    "dependencies_risk": 15,
}
RECEIPT_STATUSES = {
    "created", "approval_pending", "completed", "denied", "cancelled",
    "refunded", "partially_refunded", "pending", "failed",
}


def _utc_id() -> str:
    return str(uuid4())


def money_to_cents(value: object) -> int:
    """Convert a CAD amount to cents without floating-point ambiguity."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be a valid decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be greater than zero")
    cents = int(amount * 100)
    if cents > 10_000_000:
        raise ValueError("amount exceeds the SecuredMe transaction limit")
    return cents


def validate_support_amount(cents: int, *, recurring: bool) -> int:
    if recurring and cents not in SUPPORT_PRESETS_CENTS:
        raise ValueError("monthly support must be 5, 10, or 25 CAD")
    if not recurring and not 100 <= cents <= 1_000_000:
        raise ValueError("one-time support must be between 1 and 10000 CAD")
    return cents


@dataclass(frozen=True)
class Receipt:
    id: str
    provider: str
    kind: str
    amount_cents: int
    currency: str
    status: str
    provider_reference: str
    idempotency_key: str
    external_event_id: str = ""
    user_reference: str = ""

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["amount"] = f"{self.amount_cents / 100:.2f}"
        return payload


class ReceiptStore:
    """SQLite receipt ledger with provider-event and request idempotency."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS receipts (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              kind TEXT NOT NULL,
              amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
              currency TEXT NOT NULL,
              status TEXT NOT NULL,
              provider_reference TEXT NOT NULL DEFAULT '',
              idempotency_key TEXT NOT NULL UNIQUE,
              external_event_id TEXT NOT NULL DEFAULT '',
              user_reference TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(provider, external_event_id)
            );
            CREATE TABLE IF NOT EXISTS identity_links (
              id TEXT PRIMARY KEY,
              local_subject TEXT NOT NULL,
              provider TEXT NOT NULL,
              provider_subject TEXT NOT NULL,
              consent_id TEXT NOT NULL,
              linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(provider, provider_subject),
              UNIQUE(local_subject, provider)
            );
            """
        )

    def create(self, receipt: Receipt) -> Receipt:
        if receipt.provider not in PROVIDERS:
            raise ValueError("unsupported provider")
        if receipt.status not in RECEIPT_STATUSES:
            raise ValueError("unsupported receipt status")
        existing = self.by_idempotency(receipt.idempotency_key)
        if existing:
            return existing
        self.connection.execute(
            """INSERT INTO receipts
            (id, provider, kind, amount_cents, currency, status,
             provider_reference, idempotency_key, external_event_id, user_reference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (receipt.id, receipt.provider, receipt.kind, receipt.amount_cents,
             receipt.currency, receipt.status, receipt.provider_reference,
             receipt.idempotency_key, receipt.external_event_id, receipt.user_reference),
        )
        self.connection.commit()
        return receipt

    def by_idempotency(self, key: str) -> Receipt | None:
        row = self.connection.execute(
            "SELECT * FROM receipts WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return self._receipt(row)

    def get(self, receipt_id: str) -> Receipt | None:
        row = self.connection.execute(
            "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
        return self._receipt(row)

    def apply_event(
        self,
        *,
        provider: str,
        event_id: str,
        provider_reference: str,
        status: str,
    ) -> tuple[Receipt | None, bool]:
        if status not in RECEIPT_STATUSES:
            raise ValueError("unsupported receipt status")
        duplicate = self.connection.execute(
            "SELECT 1 FROM receipts WHERE provider = ? AND external_event_id = ?",
            (provider, event_id),
        ).fetchone()
        if duplicate:
            row = self.connection.execute(
                "SELECT * FROM receipts WHERE provider = ? AND external_event_id = ?",
                (provider, event_id),
            ).fetchone()
            return self._receipt(row), False
        self.connection.execute(
            """UPDATE receipts SET status = ?, external_event_id = ?,
            updated_at = CURRENT_TIMESTAMP WHERE provider = ? AND provider_reference = ?""",
            (status, event_id, provider, provider_reference),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM receipts WHERE provider = ? AND provider_reference = ?",
            (provider, provider_reference),
        ).fetchone()
        return self._receipt(row), bool(row)

    def link_identity(
        self,
        *,
        local_subject: str,
        provider: str,
        provider_subject: str,
        consent_id: str,
    ) -> dict[str, str]:
        if provider not in {"google", "github", "paypal"}:
            raise ValueError("unsupported identity provider")
        if not all(item.strip() for item in (local_subject, provider_subject, consent_id)):
            raise ValueError("explicit local subject, provider subject, and consent are required")
        link_id = _utc_id()
        self.connection.execute(
            "INSERT INTO identity_links (id, local_subject, provider, provider_subject, consent_id) VALUES (?, ?, ?, ?, ?)",
            (link_id, local_subject, provider, provider_subject, consent_id),
        )
        self.connection.commit()
        return {"id": link_id, "local_subject": local_subject, "provider": provider,
                "provider_subject": provider_subject, "consent_id": consent_id}

    @staticmethod
    def _receipt(row: sqlite3.Row | None) -> Receipt | None:
        if row is None:
            return None
        return Receipt(**{field: row[field] for field in Receipt.__dataclass_fields__})


def new_receipt(
    *, provider: str, kind: str, amount_cents: int, idempotency_key: str,
    provider_reference: str = "", status: str = "created", user_reference: str = "",
) -> Receipt:
    if not idempotency_key.strip():
        raise ValueError("Idempotency-Key is required")
    return Receipt(_utc_id(), provider, kind, amount_cents, "CAD", status,
                   provider_reference, idempotency_key, user_reference=user_reference)


def intake_score(values: dict[str, object]) -> dict[str, Any]:
    normalized: dict[str, int] = {}
    for field, weight in INTAKE_WEIGHTS.items():
        try:
            value = int(values[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer from 0 to 100") from exc
        if not 0 <= value <= 100:
            raise ValueError(f"{field} must be between 0 and 100")
        normalized[field] = value
    score = sum(normalized[field] * weight for field, weight in INTAKE_WEIGHTS.items()) / 100
    return {
        "score": round(score, 2),
        "inputs": normalized,
        "weights": INTAKE_WEIGHTS,
        "decision": "human_review_required",
        "automatic_acceptance": False,
        "automatic_rejection": False,
    }


def escrow_milestones(total_cents: int) -> list[dict[str, Any]]:
    if total_cents <= 0:
        raise ValueError("escrow total must be greater than zero")
    first = total_cents // 2
    return [
        {"sequence": 1, "name": "Agreement and schedule accepted", "amount_cents": first, "release": "buyer_acceptance_required"},
        {"sequence": 2, "name": "Delivery accepted", "amount_cents": total_cents - first, "release": "buyer_acceptance_required"},
    ]


def verify_square_signature(notification_url: str, body: bytes, signature: str, signature_key: str) -> bool:
    if not all((notification_url, body, signature, signature_key)):
        return False
    digest = hmac.new(signature_key.encode(), notification_url.encode() + body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def verify_hmac_event(body: bytes, signature: str, secret: str) -> bool:
    """Generic local/test webhook signature verifier; never used as PayPal verification."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


def pkce_pair() -> dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return {"verifier": verifier, "challenge": challenge, "method": "S256"}


def provider_event_status(provider: str, event_type: str) -> str:
    mappings = {
        "paypal": {
            "PAYMENT.CAPTURE.COMPLETED": "completed",
            "PAYMENT.CAPTURE.DENIED": "denied",
            "PAYMENT.CAPTURE.REFUNDED": "refunded",
            "CHECKOUT.ORDER.APPROVED": "approval_pending",
        },
        "square": {
            "payment.updated:COMPLETED": "completed",
            "payment.updated:CANCELED": "cancelled",
            "refund.updated:COMPLETED": "refunded",
            "refund.updated:REJECTED": "failed",
        },
    }
    return mappings.get(provider, {}).get(event_type, "pending")


def safe_json(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("request body must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload

