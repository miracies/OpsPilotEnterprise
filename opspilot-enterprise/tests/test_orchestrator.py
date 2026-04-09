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
    resp = client.post(
        "/api/v1/orchestrate/diagnose",
        json={
            "description": "esxi-node03 CPU surge",
            "object_id": "host-33",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_chat_resource_query_requires_confirmation():
    resp = client.post(
        "/api/v1/orchestrate/chat",
        json={
            "session_id": "sess-rq-1",
            "message": "vcenter生产环境有多少虚拟机",
            "history": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_name"] == "ResourceQueryAgent"
    assert "conn-vcenter-prod" in data["assistant_message"]
    assert data["tool_traces"] == []
    assert "intent_understanding" in data["reasoning_summary"]


def test_chat_resource_query_confirm_then_execute(monkeypatch):
    import app.main as orchestrator_main

    async def _fake_inventory():
        return {
            "summary": {
                "vm_count": 42,
                "host_count": 7,
                "cluster_count": 2,
                "powered_off_vm_count": 1,
                "unhealthy_host_count": 0,
            }
        }

    monkeypatch.setattr(orchestrator_main, "_query_vcenter_prod_inventory", _fake_inventory)
    resp = client.post(
        "/api/v1/orchestrate/chat",
        json={
            "session_id": "sess-rq-2",
            "message": "确认",
            "history": [
                {
                    "role": "assistant",
                    "content": "检测到你在查询 vCenter 生产环境虚拟机数量。请确认是否查询 目标连接=conn-vcenter-prod？回复“确认”继续。",
                }
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_name"] == "ResourceQueryAgent"
    assert "VM总数：42" in data["assistant_message"]
    assert len(data["tool_traces"]) == 1
    assert "execution_plan" in data["reasoning_summary"]


def test_chat_non_resource_path_still_works(monkeypatch):
    import app.main as orchestrator_main

    async def _fake_llm_chat(_message, _history=None):
        return "普通对话响应"

    monkeypatch.setattr(orchestrator_main, "_llm_chat", _fake_llm_chat)
    resp = client.post(
        "/api/v1/orchestrate/chat",
        json={
            "session_id": "sess-001",
            "message": "你好",
            "history": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_name"] == "Orchestrator"
    assert "result_summary" in data["reasoning_summary"]


def test_chat_export_vm_list(monkeypatch):
    import app.main as orchestrator_main

    async def _fake_export(_session_id: str, _requested_columns: list[str]):
        return {
            "export_id": "exp-123",
            "file_name": "vm-list.csv",
            "download_url": "http://127.0.0.1:8000/api/v1/chat/exports/exp-123/download",
            "expires_at": "2026-04-09T10:10:00+00:00",
            "file_size_bytes": 2048,
            "mime_type": "text/csv; charset=utf-8",
            "export_columns": ["name", "ip_address", "host_name"],
            "ignored_columns": [],
        }

    monkeypatch.setattr(orchestrator_main, "_export_vcenter_prod_vm_inventory", _fake_export)
    resp = client.post(
        "/api/v1/orchestrate/chat",
        json={
            "session_id": "sess-exp-1",
            "message": "导出vCenter生产环境虚拟机列表",
            "history": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_name"] == "ResourceQueryAgent"
    assert "导出任务" in data["assistant_message"]
    assert "已导出列" in data["assistant_message"]
    assert data["export_columns"] == ["name", "ip_address", "host_name"]
    assert data["export_file"]["download_url"].endswith("/api/v1/chat/exports/exp-123/download")
    assert "intent_understanding" in data["reasoning_summary"]
