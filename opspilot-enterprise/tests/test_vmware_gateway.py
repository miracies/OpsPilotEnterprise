"""Smoke tests for VMware Skill Gateway."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "vmware-skill-gateway")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_capabilities():
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "tools" in data["data"]


def test_get_vcenter_inventory():
    resp = client.post("/api/v1/query/get_vcenter_inventory", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_query_events():
    resp = client.post("/api/v1/query/query_events", json={"object_id": "host-33", "hours": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_invoke_inventory():
    resp = client.post("/api/v1/invoke/vmware.get_vcenter_inventory", json={"input": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
