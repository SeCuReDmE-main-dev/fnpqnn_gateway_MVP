"""Runtime validation for the public SecuredMe identity contracts."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


CONTRACT_ROOT = Path(__file__).parents[1] / "contracts" / "identity"


@lru_cache(maxsize=1)
def _contract_registry() -> tuple[dict[str, dict[str, Any]], Registry]:
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in CONTRACT_ROOT.glob("*.schema.json")
    }
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    return schemas, registry


def validate_contract(schema_name: str, payload: dict[str, Any]) -> None:
    schemas, registry = _contract_registry()
    try:
        schema = schemas[schema_name]
    except KeyError as exc:
        raise ValueError(f"unknown identity contract: {schema_name}") from exc
    Draft202012Validator(schema, registry=registry).validate(payload)
