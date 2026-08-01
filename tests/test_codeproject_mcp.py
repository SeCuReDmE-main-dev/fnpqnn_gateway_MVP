from pathlib import Path
import json

from fnpqnn_gateway_mvp.codeproject_contract import (
    CONTRACT_VERSION,
    gateway_capabilities,
    gateway_detect,
    gateway_health,
    gateway_mesh_status,
)
from fnpqnn_gateway_mvp.mcp_server import handle


MESH_RESPONSE = {
    "success": True,
    "json": {
        "success": True,
        "hostname": "cpai-gateway",
        "platform": "Docker",
        "systemDescription": "Docker (Linux)",
        "enabledRoutes": ["vision/detection", "vision/custom"],
        "knownHostnames": [f"cpai-node-{index}" for index in range(11)],
        "isBroadcasting": True,
        "isMonitoring": True,
        "acceptForwardedRequests": True,
        "allowRequestForwarding": True,
    },
}


def fake_mesh_request(*args, **kwargs):
    if args and args[0] == "/v1/server/mesh/summary":
        status = MESH_RESPONSE["json"]
        return {
            "success": True,
            "json": {
                "localServer": {"isLocalServer": True, "isActive": True, "status": status},
                "serverInfos": [
                    {"isLocalServer": False, "isActive": True, "callableHostname": host, "status": {"hostname": host}}
                    for host in status["knownHostnames"]
                ],
            },
        }
    return MESH_RESPONSE


def test_health_capabilities_and_mesh_are_versioned_and_redacted() -> None:
    health = gateway_health(requester=fake_mesh_request)
    capabilities = gateway_capabilities(requester=fake_mesh_request)
    mesh = gateway_mesh_status(requester=fake_mesh_request)
    for payload in (health, capabilities, mesh):
        assert payload["contract"] == CONTRACT_VERSION
        assert payload["secret_values_exposed"] is False
        assert "body_preview" not in json.dumps(payload)
    assert capabilities["yolo_detection_available"] is True
    assert mesh["known_peer_count"] == 11
    assert mesh["active_peer_count"] == 11


def test_detection_returns_only_normalized_predictions(tmp_path: Path) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"synthetic-image-fixture")

    def fake_detection(*args, **kwargs):
        return {
            "success": True,
            "json": {
                "success": True,
                "hostname": "cpai-gateway",
                "predictions": [{"label": "object", "confidence": 0.9, "x_min": 1, "y_min": 2, "x_max": 3, "y_max": 4, "private": "drop"}],
                "raw_image": "must-not-cross-boundary",
            },
        }

    payload = gateway_detect(str(image), requester=fake_detection)
    encoded = json.dumps(payload)
    assert payload["status"] == "success"
    assert payload["prediction_count"] == 1
    assert "private" not in encoded
    assert "raw_image" not in encoded
    assert "must-not-cross-boundary" not in encoded


def test_invalid_inputs_and_unknown_tools_are_bounded() -> None:
    missing = gateway_detect("missing-image.png", requester=fake_mesh_request)
    assert missing["error_code"] == "INVALID_INPUT"
    response = handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "not_real", "arguments": {}}})
    assert response and response["result"]["isError"] is True
    assert "TOOL_NOT_FOUND" in response["result"]["content"][0]["text"]


def test_mcp_lists_only_the_four_gateway_tools() -> None:
    response = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert response
    names = {item["name"] for item in response["result"]["tools"]}
    assert names == {
        "gateway_cpai_health",
        "gateway_cpai_capabilities",
        "gateway_cpai_mesh_status",
        "gateway_cpai_detect",
    }
