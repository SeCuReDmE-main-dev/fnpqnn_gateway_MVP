"""Minimal WSGI edge for the SecuredMe commerce contracts.

Production provider calls are intentionally delegated to configured HTTPS
adapters. The service owns validation, idempotency, receipts, intake scoring,
and signed provider-event ingestion without logging request bodies or secrets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib import error, request
from urllib.parse import urlencode, urlparse
from wsgiref.simple_server import make_server

from .commerce import (
    DIAGNOSTIC_CENTS,
    ReceiptStore,
    escrow_milestones,
    intake_score,
    money_to_cents,
    new_receipt,
    provider_event_status,
    safe_json,
    validate_support_amount,
    verify_square_signature,
)
from .identity_broker import IdentityBroker, generate_private_key_pem


JsonStart = Callable[[str, list[tuple[str, str]]], None]


def _response(start_response: JsonStart, status: str, payload: dict[str, Any]) -> list[bytes]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                            ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store"),
                            ("X-Content-Type-Options", "nosniff")])
    return [body]


def _read_body(environ: dict[str, Any]) -> bytes:
    length = min(int(environ.get("CONTENT_LENGTH") or 0), 1_000_000)
    return environ["wsgi.input"].read(length)


class PayPalAdapter:
    def __init__(self, client_id: str, client_secret: str, *, sandbox: bool = True,
                 webhook_id: str = "", subscription_plans: dict[int, str] | None = None) -> None:
        self.client_id, self.client_secret = client_id, client_secret
        self.webhook_id = webhook_id
        self.subscription_plans = subscription_plans or {}
        self.base = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _access_token(self) -> str:
        import base64
        token_req = request.Request(
            self.base + "/v1/oauth2/token", data=b"grant_type=client_credentials", method="POST",
            headers={"Authorization": "Basic " + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode(),
                     "Content-Type": "application/x-www-form-urlencoded"},
        )
        with request.urlopen(token_req, timeout=15) as response:
            return json.load(response)["access_token"]

    def create_order(self, *, amount_cents: int, description: str, request_id: str) -> dict[str, str]:
        token = self._access_token()
        body = json.dumps({"intent": "CAPTURE", "purchase_units": [{"description": description,
            "amount": {"currency_code": "CAD", "value": f"{amount_cents / 100:.2f}"}}]}).encode()
        order_req = request.Request(self.base + "/v2/checkout/orders", data=body, method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "PayPal-Request-Id": request_id})
        with request.urlopen(order_req, timeout=15) as response:
            order = json.load(response)
        approve = next((link["href"] for link in order.get("links", []) if link.get("rel") in {"approve", "payer-action"}), "")
        return {"provider_reference": order["id"], "approval_url": approve}

    def create_subscription(self, *, amount_cents: int, request_id: str,
                            return_url: str, cancel_url: str) -> dict[str, str]:
        plan_id = self.subscription_plans.get(amount_cents, "")
        if not plan_id:
            raise ValueError("PayPal monthly plan is not configured for this amount")
        body = json.dumps({"plan_id": plan_id, "application_context": {
            "brand_name": "SecuredMe", "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW", "return_url": return_url, "cancel_url": cancel_url,
        }}).encode()
        subscription_req = request.Request(self.base + "/v1/billing/subscriptions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json",
                     "PayPal-Request-Id": request_id})
        with request.urlopen(subscription_req, timeout=15) as response:
            subscription = json.load(response)
        approve = next((link["href"] for link in subscription.get("links", []) if link.get("rel") == "approve"), "")
        return {"provider_reference": subscription["id"], "approval_url": approve}

    def verify_webhook(self, *, body: bytes, headers: dict[str, str]) -> bool:
        if not self.webhook_id:
            return False
        event = safe_json(body)
        verification = {
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
            "cert_url": headers.get("PAYPAL-CERT-URL", ""),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
            "webhook_id": self.webhook_id,
            "webhook_event": event,
        }
        verify_req = request.Request(self.base + "/v1/notifications/verify-webhook-signature",
            data=json.dumps(verification).encode(), method="POST",
            headers={"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"})
        with request.urlopen(verify_req, timeout=15) as response:
            result = json.load(response)
        return result.get("verification_status") == "SUCCESS"


class CommerceApplication:
    def __init__(self, store: ReceiptStore, paypal: PayPalAdapter | None = None,
                 identity: IdentityBroker | None = None) -> None:
        self.store, self.paypal = store, paypal
        self.identity = identity or IdentityBroker(store.connection)

    def __call__(self, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        method, path = environ.get("REQUEST_METHOD", "GET"), environ.get("PATH_INFO", "/")
        origin = environ.get("HTTP_ORIGIN", "")
        parsed_origin = urlparse(origin)
        allowed_origin = origin if parsed_origin.scheme == "https" and (
            parsed_origin.hostname == "securedme.ca" or (parsed_origin.hostname or "").endswith(".securedme.ca")
        ) else ""
        original_start = start_response
        def cors_start(status: str, headers: list[tuple[str, str]]) -> None:
            if allowed_origin:
                headers.extend([("Access-Control-Allow-Origin", allowed_origin), ("Vary", "Origin")])
            original_start(status, headers)
        start_response = cors_start
        if method == "OPTIONS":
            original_start("204 No Content", [("Access-Control-Allow-Origin", allowed_origin or "https://securedme.ca"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key"),
                ("Access-Control-Max-Age", "600"), ("Content-Length", "0")])
            return [b""]
        try:
            if method == "GET" and path == "/health":
                return _response(start_response, "200 OK", {"status": "ok", "service": "securedme-commerce"})
            if method == "GET" and path == "/.well-known/openid-configuration":
                return _response(start_response, "200 OK", self.identity.discovery())
            if method == "GET" and path == "/oidc/jwks.json":
                return _response(start_response, "200 OK", self.identity.jwks())
            if method == "GET" and path == "/oidc/logout":
                return _response(start_response, "200 OK", {"signed_out": True, "local_sessions_must_be_cleared_by_client": True})
            if method == "GET" and path.startswith("/v1/payments/"):
                receipt = self.store.get(path.rsplit("/", 1)[-1])
                return _response(start_response, "200 OK" if receipt else "404 Not Found",
                                 {"receipt": receipt.public_dict()} if receipt else {"error": "receipt_not_found"})
            body = _read_body(environ)
            if method == "POST" and path in {"/v1/support/orders", "/v1/support/subscriptions", "/v1/diagnostics/orders"}:
                return self._create(path, safe_json(body), environ, start_response)
            if method == "POST" and path == "/v1/intakes":
                return _response(start_response, "200 OK", {"intake": intake_score(safe_json(body))})
            if method == "POST" and path == "/oidc/authorize":
                return self._authorize(body, environ, start_response)
            if method == "POST" and path == "/oidc/token":
                payload = safe_json(body)
                tokens = self.identity.exchange(code=str(payload.get("code", "")), client_id=str(payload.get("client_id", "")),
                    redirect_uri=str(payload.get("redirect_uri", "")), code_verifier=str(payload.get("code_verifier", "")))
                return _response(start_response, "200 OK", tokens)
            if method == "POST" and path == "/v1/identity-links":
                if environ.get("HTTP_X_SECUREDME_UPSTREAM_IDENTITY_VERIFIED") != "1":
                    return _response(start_response, "401 Unauthorized", {"error": "verified upstream identity required"})
                payload = safe_json(body)
                link = self.store.link_identity(local_subject=str(payload.get("local_subject", "")),
                    provider=str(payload.get("provider", "")), provider_subject=str(payload.get("provider_subject", "")),
                    consent_id=str(payload.get("consent_id", "")))
                return _response(start_response, "201 Created", {"link": link, "email_auto_merge": False})
            if method == "POST" and path.endswith("/escrow") and path.startswith("/v1/projects/"):
                payload = safe_json(body); cents = money_to_cents(payload.get("amount"))
                return _response(start_response, "200 OK", {"currency": "CAD", "funding": "buyer_funds_100_percent",
                    "milestones": escrow_milestones(cents), "provider": "escrow", "automatic_release": False})
            if method == "POST" and path == "/v1/square/webhooks":
                return self._square(body, environ, start_response)
            if method == "POST" and path == "/v1/paypal/webhooks":
                return self._paypal(body, environ, start_response)
            return _response(start_response, "404 Not Found", {"error": "route_not_found"})
        except ValueError as exc:
            return _response(start_response, "400 Bad Request", {"error": str(exc)})
        except (error.URLError, TimeoutError, KeyError):
            return _response(start_response, "502 Bad Gateway", {"error": "payment_provider_unavailable"})

    def _create(self, path: str, payload: dict[str, Any], environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        key = environ.get("HTTP_IDEMPOTENCY_KEY", "").strip()
        recurring = path.endswith("subscriptions")
        if path.endswith("diagnostics/orders"):
            cents, kind = DIAGNOSTIC_CENTS, "diagnostic"
        else:
            cents = validate_support_amount(money_to_cents(payload.get("amount")), recurring=recurring)
            kind = "support_monthly" if recurring else "support_once"
        existing = self.store.by_idempotency(key)
        if existing:
            return _response(start_response, "200 OK", {"receipt": existing.public_dict(), "replayed": True})
        provider_ref, approval_url, status = "", "", "created"
        if self.paypal and self.paypal.configured():
            if recurring:
                return_url = _safe_securedme_url(str(payload.get("return_url", "https://securedme.ca/pay/")))
                order = self.paypal.create_subscription(amount_cents=cents, request_id=key,
                    return_url=return_url, cancel_url=return_url)
            else:
                order = self.paypal.create_order(amount_cents=cents, description=f"SecuredMe {kind}", request_id=key)
            provider_ref, approval_url, status = order["provider_reference"], order["approval_url"], "approval_pending"
        receipt = self.store.create(new_receipt(provider="paypal", kind=kind, amount_cents=cents,
            idempotency_key=key, provider_reference=provider_ref, status=status,
            user_reference=str(payload.get("user_reference", ""))[:128]))
        return _response(start_response, "201 Created", {"receipt": receipt.public_dict(),
            "approval_url": approval_url, "provider_configured": bool(self.paypal and self.paypal.configured())})

    def _square(self, body: bytes, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        signature = environ.get("HTTP_X_SQUARE_HMACSHA256_SIGNATURE", "")
        key, url = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", ""), os.environ.get("SQUARE_WEBHOOK_URL", "")
        if not verify_square_signature(url, body, signature, key):
            return _response(start_response, "401 Unauthorized", {"error": "invalid_square_signature"})
        event = safe_json(body); data = event.get("data", {}).get("object", {})
        payment = data.get("payment") or data.get("refund") or {}
        ref = str(payment.get("id", "")); state = str(payment.get("status", ""))
        event_type = f"{event.get('type', '')}:{state}"
        receipt, applied = self.store.apply_event(provider="square", event_id=str(event.get("event_id", "")),
            provider_reference=ref, status=provider_event_status("square", event_type))
        return _response(start_response, "200 OK", {"received": True, "applied": applied,
            "receipt_id": receipt.id if receipt else None})

    def _paypal(self, body: bytes, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        paypal_headers = {name[5:].replace("_", "-"): str(value) for name, value in environ.items() if name.startswith("HTTP_PAYPAL_")}
        if not self.paypal or not self.paypal.configured() or not self.paypal.verify_webhook(body=body, headers=paypal_headers):
            return _response(start_response, "401 Unauthorized", {"error": "paypal_verification_required"})
        event = safe_json(body); resource = event.get("resource", {})
        ref = str(resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id") or resource.get("id", ""))
        receipt, applied = self.store.apply_event(provider="paypal", event_id=str(event.get("id", "")),
            provider_reference=ref, status=provider_event_status("paypal", str(event.get("event_type", ""))))
        return _response(start_response, "200 OK", {"received": True, "applied": applied,
            "receipt_id": receipt.id if receipt else None})

    def _authorize(self, body: bytes, environ: dict[str, Any], start_response: JsonStart) -> list[bytes]:
        if environ.get("HTTP_X_SECUREDME_UPSTREAM_IDENTITY_VERIFIED") != "1":
            return _response(start_response, "401 Unauthorized", {"error": "verified upstream identity required"})
        payload = safe_json(body)
        code = self.identity.authorize(client_id=str(payload.get("client_id", "")),
            redirect_uri=str(payload.get("redirect_uri", "")), local_subject=str(payload.get("local_subject", "")),
            provider=str(payload.get("provider", "")), code_challenge=str(payload.get("code_challenge", "")),
            nonce=str(payload.get("nonce", "")),
            chatgpt_context_attested=environ.get("HTTP_X_CHATGPT_CONTEXT_ATTESTED") == "1")
        query = urlencode({"code": code, "state": str(payload.get("state", ""))})
        return _response(start_response, "201 Created", {"code": code,
            "redirect_to": str(payload.get("redirect_uri")) + "?" + query})


def _safe_securedme_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not (parsed.hostname == "securedme.ca" or (parsed.hostname or "").endswith(".securedme.ca")):
        raise ValueError("return_url must be an HTTPS SecuredMe URL")
    return value


def application_from_env() -> CommerceApplication:
    data_path = Path(os.environ.get("SECUREDME_COMMERCE_DB", ".fnpqnn_gateway/commerce.sqlite3"))
    data_path.parent.mkdir(parents=True, exist_ok=True)
    paypal = PayPalAdapter(os.environ.get("PAYPAL_CHECKOUT_CLIENT_ID", ""),
        os.environ.get("PAYPAL_CHECKOUT_CLIENT_SECRET", ""),
        sandbox=os.environ.get("PAYPAL_CHECKOUT_MODE", "sandbox").lower() != "live",
        webhook_id=os.environ.get("PAYPAL_CHECKOUT_WEBHOOK_ID", ""),
        subscription_plans={500: os.environ.get("PAYPAL_PLAN_5_CAD", ""),
            1000: os.environ.get("PAYPAL_PLAN_10_CAD", ""), 2500: os.environ.get("PAYPAL_PLAN_25_CAD", "")})
    store = ReceiptStore(data_path)
    key_path = os.environ.get("OIDC_SIGNING_KEY_PATH", "")
    identity = IdentityBroker.from_pem(store.connection, Path(key_path).read_bytes()) if key_path else IdentityBroker(store.connection)
    return CommerceApplication(store, paypal, identity)


def main() -> None:
    host, port = os.environ.get("SECUREDME_COMMERCE_HOST", "127.0.0.1"), int(os.environ.get("PORT", "8788"))
    with make_server(host, port, application_from_env()) as server:
        print(f"SecuredMe commerce listening on http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
