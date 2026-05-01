"""Smoke tests for Approval Center BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_list_approvals():
    client = _get_client()
    resp = client.get("/api/v1/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "items" in data["data"]
    assert len(data["data"]["items"]) > 0


def test_list_approvals_filter_by_status():
    client = _get_client()
    resp = client.get("/api/v1/approvals?status=pending")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all(i["status"] == "pending" for i in items)


def test_get_approval_detail():
    client = _get_client()
    resp = client.get("/api/v1/approvals/APR-20260405-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "APR-20260405-001"
    assert "risk_score" in data


def test_get_approval_not_found():
    client = _get_client()
    resp = client.get("/api/v1/approvals/NONEXISTENT")
    assert resp.status_code == 404


def test_decide_approval():
    client = _get_client()
    resp = client.post("/api/v1/approvals/APR-20260405-001/decide", json={
        "decision": "approved",
        "comment": "已验证，允许执行",
        "decided_by": "ops-lead",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["decision"] == "approved"
