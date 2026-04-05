"""Smoke tests for Event Ingestion Service."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "event-ingestion-service")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_incidents():
    resp = client.get("/api/v1/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_get_incident():
    resp = client.get("/api/v1/incidents/inc-a1b2c3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_ingest_event():
    resp = client.post("/api/v1/events/ingest", json={
        "source": "vmware-monitor",
        "source_type": "metric_anomaly",
        "object_type": "HostSystem",
        "object_id": "host-33",
        "severity": "high",
        "summary": "CPU usage > 95%",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_analyze_incident():
    resp = client.post("/api/v1/incidents/inc-a1b2c3/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
