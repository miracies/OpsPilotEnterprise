"""Smoke tests for Event Ingestion Service."""
import importlib
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "event-ingestion-service")
_app = load_service_app(SERVICE_DIR)
event_main = importlib.import_module("app.main")
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
    ingest = client.post("/api/v1/events/ingest", json={
        "source": "vmware-monitor",
        "source_type": "metric_anomaly",
        "object_type": "HostSystem",
        "object_id": "host-get-1",
        "severity": "high",
        "summary": "CPU usage > 90%",
    })
    incident_id = ingest.json()["data"]["incident_id"]
    resp = client.get(f"/api/v1/incidents/{incident_id}")
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


def test_analyze_incident(monkeypatch):
    ingest = client.post("/api/v1/events/ingest", json={
        "source": "vmware-monitor",
        "source_type": "metric_anomaly",
        "object_type": "HostSystem",
        "object_id": "host-analyze-1",
        "severity": "high",
        "summary": "CPU usage > 92%",
    })
    incident_id = ingest.json()["data"]["incident_id"]

    async def fake_analyze(incident_id: str, mode: str = "auto", user_id: str = "ops-user"):
        return {"incident_id": incident_id, "status": "pending_action", "analysis": {"status": "completed", "round": 1, "max_rounds": 5, "analysis_process": []}}

    monkeypatch.setattr(event_main, "_analyze_incident", fake_analyze)
    resp = client.post(f"/api/v1/incidents/{incident_id}/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
