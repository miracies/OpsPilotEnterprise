"""Smoke tests for Evidence Aggregator."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "evidence-aggregator")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_aggregate():
    resp = client.post("/api/v1/evidence/aggregate", json={
        "incident_id": "inc-001",
        "source_refs": ["host-33", "vm-201"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_get_evidence():
    resp = client.get("/api/v1/evidence/evd-test-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
