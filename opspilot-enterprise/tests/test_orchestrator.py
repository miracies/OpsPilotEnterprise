"""Smoke tests for LangGraph Orchestrator."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "langgraph-orchestrator")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_diagnose():
    resp = client.post("/api/v1/orchestrate/diagnose", json={
        "description": "esxi-node03 CPU 飙升",
        "object_id": "host-33",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_chat():
    resp = client.post("/api/v1/orchestrate/chat", json={
        "session_id": "sess-001",
        "message": "帮我查一下 esxi-node03 的状态",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
