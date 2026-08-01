"""stdio MCP server exposing the real CodeProject.AI gateway boundary."""

from __future__ import annotations

from typing import Any, Callable
import inspect
import json
import sys

from .codeproject_contract import (
    gateway_capabilities,
    gateway_detect,
    gateway_health,
    gateway_mesh_status,
)

Tool = Callable[..., dict[str, Any]]
TOOLS: dict[str, Tool] = {
    "gateway_cpai_health": gateway_health,
    "gateway_cpai_capabilities": gateway_capabilities,
    "gateway_cpai_mesh_status": gateway_mesh_status,
    "gateway_cpai_detect": gateway_detect,
}


def _input_schema(fn: Tool) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in inspect.signature(fn).parameters.items():
        if name == "requester":
            continue
        annotation = str(parameter.annotation)
        if "int" in annotation:
            schema = {"type": "integer"}
        elif "float" in annotation:
            schema = {"type": "number"}
        else:
            schema = {"type": "string"}
        properties[name] = schema
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fnpqnn-gateway-mvp", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "tools": [
                    {"name": name, "description": fn.__doc__ or name, "inputSchema": _input_schema(fn)}
                    for name, fn in TOOLS.items()
                ]
            },
        }
    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name") or "")
        if name not in TOOLS:
            payload = {
                "status": "error",
                "error_code": "TOOL_NOT_FOUND",
                "message": "Unknown Gateway MCP tool.",
                "secret_values_exposed": False,
            }
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"isError": True, "content": [{"type": "text", "text": json.dumps(payload)}]},
            }
        try:
            payload = TOOLS[name](**(params.get("arguments") or {}))
        except Exception:
            payload = {
                "status": "error",
                "error_code": "GATEWAY_INTERNAL_ERROR",
                "message": "Gateway operation failed.",
                "secret_values_exposed": False,
            }
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "isError": payload.get("status") == "error",
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            },
        }
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": -32601, "message": "Method not found"}}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except Exception:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
