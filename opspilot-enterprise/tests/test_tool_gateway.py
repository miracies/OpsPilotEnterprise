"""Smoke tests for Tool Gateway."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "tool-gateway")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


def test_list_tools():
    resp = client.get("/api/v1/tools/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    tools = data["data"]
    assert isinstance(tools, list)
    assert len(tools) >= 18
    assert any(tool["name"] == "vmware.get_vcenter_inventory" for tool in tools)
    assert any(tool["name"] == "k8s.get_workload_status" for tool in tools)


def test_tools_health():
    resp = client.get("/api/v1/tools/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_invoke_mock():
    resp = client.post("/api/v1/invoke/some.mock.tool", json={"input": {"key": "value"}})
    assert resp.status_code == 200
    data = resp.json()
    assert "trace_id" in data
    assert "request_id" in data
