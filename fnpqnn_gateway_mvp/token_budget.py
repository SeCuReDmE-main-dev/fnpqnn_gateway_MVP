"""Token governor policy and budget contracts.

The contracts in this module are intentionally plain dictionaries so CLI
outputs stay JSON-stable and easy for companion tools to consume.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TOKEN_GOVERNOR_DIR = ".fnpqnn_gateway/token_governor"
POLICY_SCHEMA = "securedme.token_governor.policy.v1"
BUDGET_SCHEMA = "securedme.token_governor.budget.v1"

ACTIVITY_PROFILES: dict[str, dict[str, Any]] = {
    "short_question": {
        "description": "Single concept, short answer, or small command handoff.",
        "max_input_tokens": 2200,
        "max_visible_tool_tokens": 500,
        "max_history_items": 4,
        "max_visible_chars": 1800,
    },
    "simulation": {
        "description": "Math or simulator run where raw state must become a snapshot.",
        "max_input_tokens": 7000,
        "max_visible_tool_tokens": 1200,
        "max_history_items": 8,
        "max_visible_chars": 4200,
    },
    "math_proof": {
        "description": "Symbolic math, proof review, or neutrosophic invariant check.",
        "max_input_tokens": 9000,
        "max_visible_tool_tokens": 1400,
        "max_history_items": 10,
        "max_visible_chars": 5600,
    },
    "research": {
        "description": "Fresh-evidence research, cited validation, or deepsearch plan.",
        "max_input_tokens": 8500,
        "max_visible_tool_tokens": 1300,
        "max_history_items": 8,
        "max_visible_chars": 5200,
    },
    "debug": {
        "description": "Code/debug workflow with concise logs and file references.",
        "max_input_tokens": 7600,
        "max_visible_tool_tokens": 1600,
        "max_history_items": 10,
        "max_visible_chars": 5000,
    },
    "teacher_review": {
        "description": "Teacher-facing review with classroom-safe explanation.",
        "max_input_tokens": 6200,
        "max_visible_tool_tokens": 1000,
        "max_history_items": 8,
        "max_visible_chars": 4200,
    },
}

USER_PROFILES: dict[str, dict[str, Any]] = {
    "student_minor": {
        "description": "Supervised minor student; strictest context and safety defaults.",
        "budget_multiplier": 0.7,
        "allow_operator_diagnostics": False,
    },
    "student_adult": {
        "description": "Adult learner; compact context with normal educational detail.",
        "budget_multiplier": 0.85,
        "allow_operator_diagnostics": False,
    },
    "teacher": {
        "description": "Teacher or reviewer; can receive compact evidence summaries.",
        "budget_multiplier": 1.0,
        "allow_operator_diagnostics": False,
    },
    "operator": {
        "description": "Maintainer/operator diagnostics; longer context allowed.",
        "budget_multiplier": 1.25,
        "allow_operator_diagnostics": True,
    },
}

ROUTE_BUDGETS: dict[str, dict[str, Any]] = {
    "codex": {
        "route": "codex",
        "provider": "openai",
        "max_input_tokens": 10000,
        "max_visible_tool_tokens": 1800,
        "cache_candidate_min_tokens": 1024,
    },
    "antigravity": {
        "route": "antigravity",
        "provider": "gemini",
        "max_input_tokens": 10000,
        "max_visible_tool_tokens": 1800,
        "cache_candidate_min_tokens": 2048,
    },
    "gemini": {
        "route": "gemini",
        "provider": "gemini",
        "max_input_tokens": 10000,
        "max_visible_tool_tokens": 1800,
        "cache_candidate_min_tokens": 2048,
    },
    "simulator": {
        "route": "simulator",
        "provider": "local",
        "max_input_tokens": 6500,
        "max_visible_tool_tokens": 1200,
        "cache_candidate_min_tokens": 0,
    },
}


def _scaled(value: int, multiplier: float) -> int:
    return max(1, int(value * multiplier))


def list_activity_profiles() -> dict[str, dict[str, Any]]:
    return deepcopy(ACTIVITY_PROFILES)


def list_user_profiles() -> dict[str, dict[str, Any]]:
    return deepcopy(USER_PROFILES)


def default_policy(preset: str = "classroom") -> dict[str, Any]:
    if preset not in {"classroom", "operator"}:
        raise ValueError("preset must be classroom or operator")
    default_user = "operator" if preset == "operator" else "student_minor"
    return {
        "schema": POLICY_SCHEMA,
        "preset": preset,
        "default_route": "codex",
        "default_activity": "short_question",
        "default_user_profile": default_user,
        "official_school_routes": ["codex", "antigravity", "gemini"],
        "activity_profiles": list_activity_profiles(),
        "user_profiles": list_user_profiles(),
        "route_budgets": deepcopy(ROUTE_BUDGETS),
        "rules": [
            "stable system context must precede variable session data",
            "large app state must become artifact pointers or component metadata",
            "visible tool output must be summary plus ids plus next actions",
            "long math simulations must become verified snapshots",
            "preserve I -> I_system^S -> D_f -> dF -> i_fractal",
            "never serialize provider secrets, cookies, browser sessions, or dotenv values",
        ],
    }


def resolve_budget(
    *,
    route: str,
    activity: str,
    user_profile: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_policy = policy or default_policy("classroom")
    route_key = route.strip().lower()
    activity_key = activity.strip().lower()
    user_key = user_profile.strip().lower()
    route_budget = selected_policy["route_budgets"].get(route_key) or ROUTE_BUDGETS.get(route_key)
    activity_budget = selected_policy["activity_profiles"].get(activity_key) or ACTIVITY_PROFILES.get(activity_key)
    user_budget = selected_policy["user_profiles"].get(user_key) or USER_PROFILES.get(user_key)
    if route_budget is None:
        raise ValueError(f"unknown token governor route '{route}'")
    if activity_budget is None:
        raise ValueError(f"unknown token governor activity '{activity}'")
    if user_budget is None:
        raise ValueError(f"unknown token governor user profile '{user_profile}'")
    multiplier = float(user_budget["budget_multiplier"])
    max_input = min(int(route_budget["max_input_tokens"]), _scaled(int(activity_budget["max_input_tokens"]), multiplier))
    max_visible_tool = min(
        int(route_budget["max_visible_tool_tokens"]),
        _scaled(int(activity_budget["max_visible_tool_tokens"]), multiplier),
    )
    return {
        "schema": BUDGET_SCHEMA,
        "route": route_key,
        "provider": route_budget["provider"],
        "activity": activity_key,
        "user_profile": user_key,
        "max_input_tokens": max_input,
        "max_visible_tool_tokens": max_visible_tool,
        "max_history_items": _scaled(int(activity_budget["max_history_items"]), multiplier),
        "max_visible_chars": _scaled(int(activity_budget["max_visible_chars"]), multiplier),
        "cache_candidate_min_tokens": int(route_budget["cache_candidate_min_tokens"]),
        "operator_diagnostics_allowed": bool(user_budget["allow_operator_diagnostics"]),
    }
