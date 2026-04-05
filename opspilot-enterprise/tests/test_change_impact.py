"""Smoke tests for Change Impact Service."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "change-impact-service")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_analyze():
    resp = client.post("/api/v1/change-impact/analyze", json={
        "change_type": "migration",
        "target_type": "VirtualMachine",
        "target_id": "vm-201",
        "requested_action": "vm_migrate",
        "environment": "prod",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    result = data["data"]
    assert "risk_score" in result
    assert "risk_level" in result
    assert "impacted_objects" in result
