"""Smoke tests for Chat + Diagnosis flow via BFF."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_create_session():
    client = _get_client()
    resp = client.post("/api/v1/chat/sessions", json={"title": "测试会话"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["title"] == "测试会话"
    assert data["data"]["id"].startswith("sess-")


def test_list_sessions():
    client = _get_client()
    client.post("/api/v1/chat/sessions", json={"title": "会话A"})
    resp = client.get("/api/v1/chat/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    assert isinstance(sessions, list)
    assert len(sessions) >= 1


def test_send_message_normal():
    """Non-diagnosis message returns a generic reply."""
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "Normal"}).json()["data"]
    sid = sess["id"]

    resp = client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"message": "你好"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    msg = data["data"]
    assert msg["role"] == "assistant"
    assert msg["session_id"] == sid
    assert "diagnosis_id" not in msg or msg["diagnosis_id"] is None


def test_send_message_triggers_diagnosis():
    """Message with diagnosis keywords triggers structured diagnosis."""
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "Diag"}).json()["data"]
    sid = sess["id"]

    resp = client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"message": "帮我分析 esxi-node03 的 CPU 告警原因"})
    assert resp.status_code == 200
    msg = resp.json()["data"]
    assert msg["role"] == "assistant"
    assert msg["diagnosis_id"] is not None
    assert msg["diagnosis_id"].startswith("dg-")
    assert len(msg.get("tool_traces", [])) > 0
    assert len(msg.get("evidence_refs", [])) > 0
    assert len(msg.get("root_cause_candidates", [])) > 0
    assert len(msg.get("recommended_actions", [])) > 0


def test_get_session_messages():
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "MsgTest"}).json()["data"]
    sid = sess["id"]
    client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"message": "诊断一下"})

    resp = client.get(f"/api/v1/chat/sessions/{sid}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
