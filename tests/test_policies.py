"""Smoke tests for Policies & Agent Runs BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_list_policies():
    client = _get_client()
    resp = client.get("/api/v1/policies")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) > 0


def test_get_policy_detail():
    client = _get_client()
    resp = client.get("/api/v1/policies/POL-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "POL-001"
    assert "effect" in data
    assert "rego_snippet" in data


def test_get_policy_hits():
    client = _get_client()
    resp = client.get("/api/v1/policies/POL-001/hits")
    assert resp.status_code == 200
    hits = resp.json()["data"]["items"]
    assert len(hits) > 0
    assert all(h["policy_id"] == "POL-001" for h in hits)


def test_list_agent_runs():
    client = _get_client()
    resp = client.get("/api/v1/agent-runs")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) > 0


def test_get_agent_run_detail():
    client = _get_client()
    resp = client.get("/api/v1/agent-runs/RUN-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "RUN-001"
    assert "steps" in data
    assert len(data["steps"]) > 0


def test_list_upgrades():
    client = _get_client()
    resp = client.get("/api/v1/upgrades")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) > 0


def test_get_upgrade_detail():
    client = _get_client()
    resp = client.get("/api/v1/upgrades/PKG-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version"] == "0.2.0"
    assert "changelog" in data
