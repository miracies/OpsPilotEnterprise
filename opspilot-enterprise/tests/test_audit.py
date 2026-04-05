"""Smoke tests for Audit BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_list_audit_logs():
    client = _get_client()
    resp = client.get("/api/v1/audit/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    items = data["data"]["items"]
    assert len(items) > 0


def test_list_audit_logs_filter_severity():
    client = _get_client()
    resp = client.get("/api/v1/audit/logs?severity=warning")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all(i["severity"] == "warning" for i in items)


def test_get_audit_log_detail():
    client = _get_client()
    resp = client.get("/api/v1/audit/logs/AUD-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "AUD-001"
    assert "actor" in data
    assert "outcome" in data


def test_get_audit_log_not_found():
    client = _get_client()
    resp = client.get("/api/v1/audit/logs/NONEXISTENT")
    assert resp.status_code == 404
