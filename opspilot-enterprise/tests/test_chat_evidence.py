"""Smoke tests for Chat evidence and tool-trace endpoints."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def _create_diagnosis_session(client):
    """Helper: create session and send a diagnosis-triggering message."""
    sess = client.post("/api/v1/chat/sessions", json={"title": "EvidenceTest"}).json()["data"]
    sid = sess["id"]
    msg = client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"message": "排查 esxi-node03 CPU 异常"}).json()["data"]
    return sid, msg


def test_evidence_populated_after_diagnosis():
    client = _get_client()
    sid, _ = _create_diagnosis_session(client)

    resp = client.get(f"/api/v1/chat/sessions/{sid}/evidence")
    assert resp.status_code == 200
    evidence = resp.json()["data"]
    assert isinstance(evidence, list)
    assert len(evidence) > 0
    assert "evidence_id" in evidence[0]
    assert "source_type" in evidence[0]
    assert "summary" in evidence[0]
    assert "confidence" in evidence[0]


def test_tool_traces_populated_after_diagnosis():
    client = _get_client()
    sid, _ = _create_diagnosis_session(client)

    resp = client.get(f"/api/v1/chat/sessions/{sid}/tool-traces")
    assert resp.status_code == 200
    traces = resp.json()["data"]
    assert isinstance(traces, list)
    assert len(traces) > 0
    assert "tool_name" in traces[0]
    assert "gateway" in traces[0]
    assert "status" in traces[0]


def test_empty_evidence_before_diagnosis():
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "EmptyEv"}).json()["data"]
    sid = sess["id"]

    resp = client.get(f"/api/v1/chat/sessions/{sid}/evidence")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_diagnosis_lookup():
    client = _get_client()
    _, msg = _create_diagnosis_session(client)
    diag_id = msg["diagnosis_id"]
    assert diag_id is not None

    resp = client.get(f"/api/v1/chat/diagnoses/{diag_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    diag = data["data"]
    assert diag["diagnosis_id"] == diag_id
    assert len(diag["root_cause_candidates"]) > 0
    assert len(diag["evidences"]) > 0
    assert len(diag["tool_traces"]) > 0


def test_diagnosis_not_found():
    client = _get_client()
    resp = client.get("/api/v1/chat/diagnoses/nonexistent-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
