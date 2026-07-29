"""SecuredMe Education suite auth-enforcer audit.

The audit is deliberately credential-blind: it validates repository-local
metadata contracts and never reads dotenv files, browser state, or provider
tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .context_compressor import reject_secret_bearing_payload
from .telemetry import emit_gateway_submit_counter


AUTH_ENFORCER_SCHEMA = "securedme.education.auth-enforcer.v1"
SUITE_AUTH_AUDIT_SCHEMA = "securedme.education.suite-auth-audit.v1"
ADAPTER_MAP_SCHEMA = "securedme.education.adapter-map.v2"
WEBAUTH_TEMPLATE_SCHEMA = "securedme.education.webauth-template.v1"
DEFAULT_ENV = "education-mvp"
DEFAULT_ROUTE = "suite-auth-audit"
NO_SECRET_MATERIAL = ("oauth_token", "cookie", "browser_session", "api_key", ".env", "client_secret")
NEUTROSOPHIC_HIERARCHY = ("I", "I_system^S", "D_f", "dF", "i_fractal")
PLATFORMS = ("codex", "antigravity")


@dataclass(frozen=True)
class SuiteRepo:
    name: str
    app: str
    slug: str
    path: str
    domain: str
    role: str = "education_app"
    auth_enforcer_owner: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "app": self.app,
            "slug": self.slug,
            "path": self.path,
            "domain": self.domain,
            "role": self.role,
            "auth_enforcer_owner": self.auth_enforcer_owner,
        }


EDUCATION_SUITE_REPOS: tuple[SuiteRepo, ...] = (
    SuiteRepo("Synthia", "Synthia", "synthia", "Synthia/Synthia", "synthia.securedme.ca"),
    SuiteRepo("FNP-QNN-MVP", "FNP-QNN", "fnpqnn", "FNP-QNN-MVP/FNP-QNN-MVP", "fnpqnn.securedme.ca"),
    SuiteRepo(
        "fnpqnn_gateway_MVP",
        "Gateway",
        "gateway",
        "FNP-QNN-MVP/fnpqnn_gateway_MVP",
        "gateway.securedme.ca",
        role="auth_enforcer",
        auth_enforcer_owner=True,
    ),
    SuiteRepo("FfeD-QLC-MVP", "FfeD-QLC", "ffed-qlc", "FfeD-QLC-MVP", "ffed-qlc.securedme.ca"),
    SuiteRepo("securedme-scholarium", "Scholarium", "scholarium", "securedme-scholarium", "scholarium.securedme.ca"),
    SuiteRepo("QuaNThoR", "QuaNThoR", "quanthor", "QuaNThoR", "quanthor.securedme.ca"),
    SuiteRepo(
        "VisualAlgorithmDesigner",
        "Visual Algorithm",
        "visual-algorithm",
        "VisualAlgorithmDesigner",
        "visual-algorithm.securedme.ca",
    ),
    SuiteRepo(
        "algorithm-builder-app",
        "Algorithm Builder",
        "algorithm-builder",
        "algorithm-builder-app",
        "algorithm-builder.securedme.ca",
    ),
    SuiteRepo(
        "algoquest-ams-discovry-labs-module-",
        "AlgoQuest",
        "algoquest",
        "algoquest-ams-discovry-labs-module-",
        "algoquest.securedme.ca",
    ),
    SuiteRepo("V.O.T-Guardian", "V.O.T Guardian", "vot-guardian", "V.O.T-Guardian", "vot-guardian.securedme.ca"),
    SuiteRepo(
        "market-guardian-retailguard",
        "Market Guardian / RetailGuard",
        "market-guardian",
        "market-guardian-retailguard",
        "market-guardian.securedme.ca",
    ),
    SuiteRepo(
        "tesla-resonance-recovery-workbench",
        "Tesla Workbench",
        "tesla-workbench",
        "tesla-resonance-recovery-workbench",
        "tesla-workbench.securedme.ca",
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except FileNotFoundError:
        return None, "missing_file"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"


def _current_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _suite_root_has_all_repos(root_path: Path) -> bool:
    return all((root_path / expected.path).exists() for expected in EDUCATION_SUITE_REPOS)


def _allow_embedded_suite_contracts(root_path: Path, *, allow_embedded_contracts: bool = False) -> bool:
    """Allow deterministic suite-contract fixtures for single-repo CI checkouts.

    The real SecuredMe Education workspace contains all sibling repositories.
    GitHub Actions for this repository checks out only fnpqnn_gateway_MVP, so
    suite-wide audit tests need a credential-free contract fixture. Explicit
    temporary roots used by negative tests are not covered by this condition.
    """

    repo_root = _current_repo_root()
    return allow_embedded_contracts and _path_is_relative_to(repo_root, root_path) and not _suite_root_has_all_repos(root_path)


def _embedded_template(expected: SuiteRepo) -> dict[str, Any]:
    return {
        "schema": WEBAUTH_TEMPLATE_SCHEMA,
        "app": {
            "name": expected.app,
            "slug": expected.slug,
            "domain": expected.domain,
        },
        "auth_policy": {
            "selected_auth_source": "web-auth",
            "fingerprint_acceptance": {"required": True},
            "managed_env_after_success_fingerprint_only": True,
            "raw_secret_stored": False,
            "forbidden_material": list(NO_SECRET_MATERIAL),
        },
        "handoff_policy": {"preserve_fields": list(NEUTROSOPHIC_HIERARCHY)},
    }


def _embedded_adapter_map(expected: SuiteRepo) -> dict[str, Any]:
    return {
        "schema": ADAPTER_MAP_SCHEMA,
        "app": {
            "name": expected.app,
            "slug": expected.slug,
            "domain": expected.domain,
        },
        "gateway": {
            "token_governor_bridge": "fnpqnn_gateway_MVP/fnpqnn_gateway_mvp/token_governor.py",
        },
        "auth_enforcer": {
            "version": AUTH_ENFORCER_SCHEMA,
            "source_repo": "fnpqnn_gateway_MVP",
            "fail_policy": "deny_on_auth_contract_failure",
            "owner": expected.auth_enforcer_owner,
        },
        "telemetry": {
            "fail_policy": "fail_open",
            "datadog": {"role": "observe_and_alert"},
        },
        "mcp": {"status": "planned"},
    }


def _platform_dir(repo_path: Path, platform: str) -> Path:
    return repo_path / f".{platform}"


def _template_path(repo_path: Path, platform: str) -> Path:
    return _platform_dir(repo_path, platform) / "webauth-template.json"


def _adapter_map_path(repo_path: Path, platform: str) -> Path:
    return _platform_dir(repo_path, platform) / "securedme-adapter-map.json"


def _error(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _validate_template(template: dict[str, Any] | None, expected: SuiteRepo) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if template is None:
        return [_error("template_missing", "webauth-template.json is missing or unreadable")]
    if template.get("schema") != WEBAUTH_TEMPLATE_SCHEMA:
        errors.append(_error("template_schema", f"expected {WEBAUTH_TEMPLATE_SCHEMA}"))
    app = template.get("app", {})
    if app.get("slug") != expected.slug:
        errors.append(_error("template_app_slug", f"expected {expected.slug}"))
    policy = template.get("auth_policy", {})
    if policy.get("selected_auth_source") != "web-auth":
        errors.append(_error("auth_source", "selected_auth_source must be web-auth"))
    fingerprint = policy.get("fingerprint_acceptance", {})
    if fingerprint.get("required") is not True:
        errors.append(_error("fingerprint_required", "fingerprint_acceptance.required must be true"))
    if policy.get("managed_env_after_success_fingerprint_only") is not True:
        errors.append(_error("managed_env_policy", "managed env must be fingerprint-only"))
    if policy.get("raw_secret_stored") is not False:
        errors.append(_error("raw_secret_stored", "raw_secret_stored must be false"))
    forbidden = set(policy.get("forbidden_material", []))
    missing_forbidden = [item for item in NO_SECRET_MATERIAL if item not in forbidden]
    if missing_forbidden:
        errors.append(_error("forbidden_material", "missing: " + ",".join(missing_forbidden)))
    preserve = template.get("handoff_policy", {}).get("preserve_fields", [])
    if tuple(preserve) != NEUTROSOPHIC_HIERARCHY:
        errors.append(_error("neutrosophic_hierarchy", "preserve_fields must match canonical order"))
    return errors


def _validate_adapter_map(adapter_map: dict[str, Any] | None, expected: SuiteRepo) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if adapter_map is None:
        return [_error("adapter_map_missing", "securedme-adapter-map.json is missing or unreadable")]
    if adapter_map.get("schema") != ADAPTER_MAP_SCHEMA:
        errors.append(_error("adapter_map_schema", f"expected {ADAPTER_MAP_SCHEMA}"))
    app = adapter_map.get("app", {})
    if app.get("slug") != expected.slug:
        errors.append(_error("adapter_app_slug", f"expected {expected.slug}"))
    gateway = adapter_map.get("gateway", {})
    if not gateway.get("token_governor_bridge"):
        errors.append(_error("token_governor_inactive", "token_governor_bridge must be active"))
    if "future_token_governor_bridge" in gateway:
        errors.append(_error("future_token_governor_bridge", "future_token_governor_bridge must be removed"))
    auth_enforcer = adapter_map.get("auth_enforcer", {})
    if auth_enforcer.get("version") != AUTH_ENFORCER_SCHEMA:
        errors.append(_error("auth_enforcer_version", f"expected {AUTH_ENFORCER_SCHEMA}"))
    if auth_enforcer.get("source_repo") != "fnpqnn_gateway_MVP":
        errors.append(_error("auth_enforcer_source", "source_repo must be fnpqnn_gateway_MVP"))
    if auth_enforcer.get("fail_policy") != "deny_on_auth_contract_failure":
        errors.append(_error("auth_enforcer_fail_policy", "unexpected auth enforcer fail policy"))
    if auth_enforcer.get("owner") is not expected.auth_enforcer_owner:
        errors.append(_error("auth_enforcer_owner", f"expected owner={expected.auth_enforcer_owner}"))
    telemetry = adapter_map.get("telemetry", {})
    if telemetry.get("fail_policy") != "fail_open":
        errors.append(_error("telemetry_fail_policy", "telemetry fail_policy must be fail_open"))
    datadog = telemetry.get("datadog", {})
    if datadog.get("role") != "observe_and_alert":
        errors.append(_error("datadog_role", "Datadog role must be observe_and_alert"))
    if adapter_map.get("mcp", {}).get("status") != "planned":
        errors.append(_error("mcp_status", "mcp.status must remain planned until connected"))
    return errors


def _adapter_summary(adapter_map: dict[str, Any] | None) -> dict[str, Any]:
    adapter_map = adapter_map or {}
    auth_enforcer = adapter_map.get("auth_enforcer", {})
    telemetry = adapter_map.get("telemetry", {})
    return {
        "schema": adapter_map.get("schema"),
        "auth_enforcer_source_repo": auth_enforcer.get("source_repo"),
        "auth_enforcer_fail_policy": auth_enforcer.get("fail_policy"),
        "auth_enforcer_owner": auth_enforcer.get("owner"),
        "token_governor_active": bool(adapter_map.get("gateway", {}).get("token_governor_bridge")),
        "telemetry_fail_policy": telemetry.get("fail_policy"),
        "datadog_role": telemetry.get("datadog", {}).get("role"),
        "mcp_status": adapter_map.get("mcp", {}).get("status"),
    }


def _decision(errors: list[dict[str, str]]) -> str:
    return "allow" if not errors else "block"


def _emit_metric(event: str, *, repo: str, platform: str, decision: str, env: str, route: str) -> bool:
    return emit_gateway_submit_counter(
        event,
        (
            f"repo:{repo}",
            f"platform:{platform}",
            f"decision:{decision}",
            f"env:{env}",
            f"route:{route}",
        ),
    )


def _log_failure(root: Path, payload: dict[str, Any]) -> Path:
    log_path = root / ".fnpqnn_gateway" / "auth_enforcer" / "auth_enforcer_failures.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": _now(),
        "schema": AUTH_ENFORCER_SCHEMA,
        "repo": payload.get("repo"),
        "platform": payload.get("platform"),
        "decision": payload.get("decision"),
        "error_codes": [error.get("code") for error in payload.get("errors", [])],
        "raw_secret_stored": False,
    }
    reject_secret_bearing_payload(record)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return log_path


def canonical_suite_inventory() -> dict[str, Any]:
    return {
        "schema": "securedme.education.suite-inventory.v2",
        "repository_count": len(EDUCATION_SUITE_REPOS),
        "auth_enforcer_owner": "fnpqnn_gateway_MVP",
        "repositories": [repo.as_dict() for repo in EDUCATION_SUITE_REPOS],
    }


def suite_auth_check(
    repo: str,
    platform: str,
    *,
    root: str | Path = ".",
    emit_metrics: bool = False,
    write_diagnostics: bool = False,
    env: str = DEFAULT_ENV,
    route: str = DEFAULT_ROUTE,
    allow_embedded_contracts: bool = False,
) -> dict[str, Any]:
    platform_key = platform.strip().lower().lstrip(".")
    if platform_key not in PLATFORMS:
        raise ValueError("platform must be codex or antigravity")
    root_path = _root(root)
    requested = Path(repo)
    expected = next(
        (
            item
            for item in EDUCATION_SUITE_REPOS
            if repo in {item.name, item.slug, item.path} or requested.as_posix() == item.path
        ),
        None,
    )
    repo_path = requested if requested.is_absolute() else root_path / requested
    if expected is None:
        expected = next((item for item in EDUCATION_SUITE_REPOS if (root_path / item.path).resolve() == repo_path.resolve()), None)
    if expected is None:
        expected = SuiteRepo(repo_path.name, repo_path.name, repo_path.name, repo_path.as_posix(), "")
    template_path = _template_path(repo_path, platform_key)
    adapter_path = _adapter_map_path(repo_path, platform_key)
    template, template_error = _load_json(template_path)
    adapter_map, adapter_error = _load_json(adapter_path)
    embedded_contracts = _allow_embedded_suite_contracts(root_path, allow_embedded_contracts=allow_embedded_contracts)
    if embedded_contracts and (not repo_path.exists() or template_error or adapter_error):
        template = template or _embedded_template(expected)
        adapter_map = adapter_map or _embedded_adapter_map(expected)
        template_error = ""
        adapter_error = ""
    errors: list[dict[str, str]] = []
    if not repo_path.exists() and not embedded_contracts:
        errors.append(_error("repo_missing", "repository path does not exist"))
    if template_error:
        errors.append(_error("template_read", template_error))
    if adapter_error:
        errors.append(_error("adapter_map_read", adapter_error))
    errors.extend(_validate_template(template, expected))
    errors.extend(_validate_adapter_map(adapter_map, expected))
    decision = _decision(errors)
    metric_event = "enforcer_check" if decision == "allow" else _metric_event_for_errors(errors)
    telemetry_sent = _emit_metric(metric_event, repo=expected.name, platform=platform_key, decision=decision, env=env, route=route) if emit_metrics else None
    diagnostic_path = ""
    payload = {
        "schema": AUTH_ENFORCER_SCHEMA,
        "success": decision == "allow",
        "created_at": _now(),
        "repo": expected.name,
        "app": expected.app,
        "slug": expected.slug,
        "path": str(repo_path),
        "expected": expected.as_dict(),
        "platform": platform_key,
        "decision": decision,
        "errors": errors,
        "template_path": str(template_path),
        "adapter_map_path": str(adapter_path),
        "adapter_map": _adapter_summary(adapter_map),
        "checks": {
            "template_present": template_path.exists() or bool(template),
            "adapter_map_present": adapter_path.exists() or bool(adapter_map),
            "token_governor_active": bool(adapter_map and adapter_map.get("gateway", {}).get("token_governor_bridge")),
            "raw_secret_stored": False,
            "datadog_fail_open": bool(adapter_map and adapter_map.get("telemetry", {}).get("fail_policy") == "fail_open"),
        },
        "telemetry": {
            "enabled": emit_metrics,
            "sent": telemetry_sent,
            "fail_policy": "fail_open",
            "raw_secret_stored": False,
        },
        "raw_secret_stored": False,
        "dry_run": not write_diagnostics,
    }
    if errors and write_diagnostics:
        diagnostic_path = str(_log_failure(root_path, payload))
    payload["diagnostic_log"] = diagnostic_path
    return payload


def _metric_event_for_errors(errors: list[dict[str, str]]) -> str:
    codes = {error["code"] for error in errors}
    if any(code in codes for code in ("template_missing", "template_read")):
        return "template_missing"
    if "secret_reject" in codes:
        return "secret_reject"
    return "adapter_drift"


def suite_auth_audit(
    *,
    root: str | Path = ".",
    emit_metrics: bool = False,
    write_diagnostics: bool = False,
    env: str = DEFAULT_ENV,
    route: str = DEFAULT_ROUTE,
    allow_embedded_contracts: bool = False,
) -> dict[str, Any]:
    root_path = _root(root)
    surfaces = [
        suite_auth_check(
            repo.path,
            platform,
            root=root_path,
            emit_metrics=emit_metrics,
            write_diagnostics=write_diagnostics,
            env=env,
            route=route,
            allow_embedded_contracts=allow_embedded_contracts,
        )
        for repo in EDUCATION_SUITE_REPOS
        for platform in PLATFORMS
    ]
    failed = [surface for surface in surfaces if not surface["success"]]
    return {
        "schema": SUITE_AUTH_AUDIT_SCHEMA,
        "success": not failed,
        "created_at": _now(),
        "root": str(root_path),
        "repository_count": len(EDUCATION_SUITE_REPOS),
        "surface_count": len(surfaces),
        "expected_surface_count": len(EDUCATION_SUITE_REPOS) * len(PLATFORMS),
        "auth_enforcer_owner": "fnpqnn_gateway_MVP",
        "inventory": canonical_suite_inventory(),
        "surfaces": surfaces,
        "summary": {
            "passed": len(surfaces) - len(failed),
            "failed": len(failed),
            "passed_surfaces": len(surfaces) - len(failed),
            "failed_surfaces": len(failed),
            "platforms": list(PLATFORMS),
            "raw_secret_stored": False,
            "datadog_role": "observe_and_alert",
            "telemetry_fail_policy": "fail_open",
        },
        "raw_secret_stored": False,
        "dry_run": not write_diagnostics,
    }
