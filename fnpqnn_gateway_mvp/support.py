"""LLM-safe support reports for gateway users."""

from __future__ import annotations

from .hooks import HOOKS
from .natural_auth import provider_status


AUTH_PROVIDERS = ("openai", "google", "github-copilot")


def support_provider(provider: str) -> dict[str, object]:
    status = provider_status(provider)
    normalized = str(status["provider"])
    return {
        "success": True,
        "provider": normalized,
        "status": status,
        "raw_token_stored": False,
        "safe_to_paste": True,
        "copilot_is_runtime_hook": normalized == "github-copilot" and "github-copilot" in HOOKS,
        "note": "This report intentionally contains status and instructions only, never raw credentials.",
    }


def support_all() -> dict[str, object]:
    providers = {provider: support_provider(provider) for provider in AUTH_PROVIDERS}
    return {
        "success": True,
        "providers": providers,
        "auth_providers": list(providers.values()),
        "runtime_hooks": sorted(HOOKS),
        "copilot_is_runtime_hook": "github-copilot" in HOOKS,
    }
