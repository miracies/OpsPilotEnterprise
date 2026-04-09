"""Smoke tests for Chat + Diagnosis flow via BFF."""
import importlib
import os
import sys
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))


def _get_client():
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for key in to_remove:
        del sys.modules[key]
    import app.main

    importlib.reload(app.main)
    return TestClient(app.main.app)


def _post_message_and_wait(client: TestClient, sid: str, message: str, timeout: float = 6.0):
    resp = client.post(f"/api/v1/chat/sessions/{sid}/messages", json={"message": message})
    assert resp.status_code == 200
    initial = resp.json()["data"]
    assert initial["role"] == "assistant"
    assert initial.get("status") == "in_progress"
    msg_id = initial["id"]

    deadline = time.time() + timeout
    latest = initial
    while time.time() < deadline:
        msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages").json()["data"]
        target = next((m for m in msgs if m["id"] == msg_id), None)
        if target:
            latest = target
            if target.get("status") in {"completed", "failed"}:
                return initial, target
        time.sleep(0.05)
    return initial, latest


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
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "Normal"}).json()["data"]
    sid = sess["id"]

    _, msg = _post_message_and_wait(client, sid, "你好")
    assert msg["session_id"] == sid
    assert msg.get("status") in {"in_progress", "completed", "failed"}
    assert len(msg.get("progress_events", [])) >= 1
    assert "reasoning_summary" in msg


def test_send_message_triggers_diagnosis():
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "Diag"}).json()["data"]
    sid = sess["id"]

    _, msg = _post_message_and_wait(client, sid, "帮我分析 esxi-node03 的 CPU 告警原因")
    assert msg["role"] == "assistant"
    assert msg.get("status") in {"in_progress", "completed", "failed"}
    assert len(msg.get("progress_events", [])) >= 1
    assert "reasoning_summary" in msg


def test_get_session_messages():
    client = _get_client()
    sess = client.post("/api/v1/chat/sessions", json={"title": "MsgTest"}).json()["data"]
    sid = sess["id"]
    _post_message_and_wait(client, sid, "诊断一个问题")

    resp = client.get(f"/api/v1/chat/sessions/{sid}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1].get("status") in {"in_progress", "completed", "failed"}


def test_fallback_resource_query_requires_confirmation(monkeypatch):
    client = _get_client()
    import app.routers.chat as chat_router

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("orchestrator down")

        async def get(self, *args, **kwargs):
            return _FakeResp({"success": True, "data": {"summary": {}}})

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "ResourceFallback"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少虚拟机")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "conn-vcenter-prod" in msg["content"]


def test_fallback_resource_query_confirm_then_execute(monkeypatch):
    client = _get_client()
    import app.routers.chat as chat_router

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("orchestrator down")

        async def get(self, *args, **kwargs):
            return _FakeResp(
                {
                    "success": True,
                    "data": {
                        "summary": {
                            "vm_count": 99,
                            "host_count": 8,
                            "cluster_count": 3,
                            "powered_off_vm_count": 2,
                            "unhealthy_host_count": 1,
                        }
                    },
                }
            )

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "ResourceFallback2"}).json()["data"]
    sid = sess["id"]
    _post_message_and_wait(client, sid, "vcenter生产环境有多少虚拟机")
    _, msg = _post_message_and_wait(client, sid, "确认")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "VM总数：99" in msg["content"]
    assert "主机数量：8" in msg["content"]


def test_fallback_export_vm_list(monkeypatch):
    client = _get_client()
    import app.routers.chat as chat_router

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *args, **kwargs):
            if "/api/v1/orchestrate/chat" in url:
                raise httpx.ConnectError("orchestrator down")
            if "/api/v1/resources/vcenter/inventory/export" in url:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "export_id": "exp-xyz",
                            "file_name": "vm-list.csv",
                            "download_url": "http://127.0.0.1:8000/api/v1/chat/exports/exp-xyz/download",
                            "expires_at": "2026-04-09T10:10:00+00:00",
                            "file_size_bytes": 111,
                            "mime_type": "text/csv; charset=utf-8",
                            "export_columns": ["name", "ip_address", "host_name"],
                            "ignored_columns": [],
                        },
                    }
                )
            return _FakeResp({"success": False, "error": "unexpected"})

        async def get(self, *args, **kwargs):
            return _FakeResp({"success": True, "data": {"summary": {}}})

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "ExportFallback"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "导出vCenter生产环境虚拟机列表")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "导出任务" in msg["content"]
    assert "已导出列" in msg["content"]
    assert msg["export_file"]["download_url"].endswith("/api/v1/chat/exports/exp-xyz/download")


def test_download_export_file():
    client = _get_client()
    import app.routers.chat as chat_router
    from app.services.chat_exports import register_export

    out_dir = Path(__file__).resolve().parent / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / "download-test.csv"
    file_path.write_text("vm_id,name,power_state\nvm-1,vm-1,poweredOn\n", encoding="utf-8")

    rec = register_export(file_path=file_path, file_name="download-test.csv")
    resp = client.get(f"/api/v1/chat/exports/{rec.export_id}/download")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "").lower()
    assert "vm_id,name,power_state" in resp.text


def test_vcenter_inventory_export_endpoint(monkeypatch):
    client = _get_client()
    import app.routers.resources as resources_router

    async def _fake_inventory(_connection_id=None):
        return {
            "virtual_machines": [
                {"vm_id": "vm-1", "name": "vm-a", "power_state": "poweredOn"},
                {"vm_id": "vm-2", "name": "vm-b", "power_state": "poweredOff"},
            ],
            "summary": {"vm_count": 2},
            "connection": {"connection_id": "conn-vcenter-prod"},
        }, {"endpoint": "https://vc.local", "username": "u", "password": "p", "insecure": True}

    async def _fake_vm_details(_inventory, _connection_input):
        return {
            "vm-1": {"name": "vm-a", "host_name": "esxi-01", "ip_addresses": ["10.0.0.1"], "cpu_count": 4},
            "vm-2": {"name": "vm-b", "host_name": "esxi-02", "ip_addresses": ["10.0.0.2"], "cpu_count": 8},
        }

    monkeypatch.setattr(resources_router, "_fetch_vcenter_inventory_data", _fake_inventory)
    monkeypatch.setattr(resources_router, "_fetch_vm_details", _fake_vm_details)
    resp = client.post(
        "/api/v1/resources/vcenter/inventory/export",
        json={
            "connection_id": "conn-vcenter-prod",
            "format": "csv",
            "requested_columns": ["name", "ip地址", "所在esxi主机名", "cpu"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["file_name"].endswith(".csv")
    assert data["export_columns"] == ["name", "ip_address", "host_name", "cpu_count"]
    assert data["ignored_columns"] == []
    assert "/api/v1/chat/exports/" in data["download_url"]
