"""Smoke tests for Notification BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_list_notifications():
    client = _get_client()
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    items = data["data"]["items"]
    assert len(items) > 0


def test_acknowledge_notification():
    client = _get_client()
    resp = client.post("/api/v1/notifications/NTF-001/acknowledge")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "acknowledged"


def test_list_oncall_shifts():
    client = _get_client()
    resp = client.get("/api/v1/oncall/shifts")
    assert resp.status_code == 200
    shifts = resp.json()["data"]["items"]
    assert len(shifts) > 0
    assert any(s["active"] for s in shifts)
