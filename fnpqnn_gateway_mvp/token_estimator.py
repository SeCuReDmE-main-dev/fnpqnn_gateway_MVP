"""Provider-aware token estimation for the gateway.

The estimator avoids network calls. If a provider-native tokenizer is not
installed, it returns a conservative documented approximation.
"""

from __future__ import annotations

import json
from typing import Any


ESTIMATE_SCHEMA = "securedme.token_governor.usage_estimate.v1"


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fallback_count(text: str) -> int:
    # Conservative for mixed English/French/JSON/math. Gemini docs approximate
    # one token per four characters; JSON punctuation and math symbols push a
    # little higher, so divide by 3.6 and add a small framing overhead.
    return max(1, int(len(text) / 3.6) + 8)


def estimate_openai_tokens(payload: Any, *, model: str = "gpt-4o-mini") -> dict[str, Any]:
    text = _to_text(payload)
    method = "fallback-char-ratio"
    count = _fallback_count(text)
    try:
        import tiktoken  # type: ignore

        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("o200k_base")
        count = len(encoding.encode(text)) + 8
        method = "tiktoken"
    except Exception:
        pass
    return {
        "schema": ESTIMATE_SCHEMA,
        "provider": "openai",
        "model": model,
        "estimated_tokens": count,
        "method": method,
        "input_chars": len(text),
        "functions_or_tools_extra_tokens": "not-included-except-json-schema-text",
    }


def estimate_gemini_tokens(payload: Any, *, model: str = "gemini") -> dict[str, Any]:
    text = _to_text(payload)
    return {
        "schema": ESTIMATE_SCHEMA,
        "provider": "gemini",
        "model": model,
        "estimated_tokens": _fallback_count(text),
        "method": "gemini-docs-char-ratio-fallback",
        "input_chars": len(text),
        "provider_count_tokens_available": False,
    }


def estimate_tokens(payload: Any, *, provider: str, model: str | None = None) -> dict[str, Any]:
    selected = provider.strip().lower()
    if selected == "openai":
        return estimate_openai_tokens(payload, model=model or "gpt-4o-mini")
    if selected in {"gemini", "google"}:
        return estimate_gemini_tokens(payload, model=model or "gemini")
    estimate = {
        "schema": ESTIMATE_SCHEMA,
        "provider": selected or "local",
        "model": model or "local",
        "estimated_tokens": _fallback_count(_to_text(payload)),
        "method": "local-char-ratio-fallback",
        "input_chars": len(_to_text(payload)),
    }
    return estimate
