"""Deterministic regressions for orchestrator_v2 intent execution chains."""
from __future__ import annotations

import os
import importlib

from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "langgraph-orchestrator")
_app = load_service_app(SERVICE_DIR)
_chat_v2_module = importlib.import_module("app.pipeline.orchestrate_chat_v2")
client = TestClient(_app)


def _chat_v2(message: str, *, session_id: str = "intent-regression") -> dict:
    resp = client.post(
        "/api/v1/orchestrate/chat-v2",
        json={
            "session_id": session_id,
            "message": message,
            "history": [],
            "user_id": "pytest",
            "channel": "web",
            "resource_catalog": [],
            "ui_context": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    return body["data"]


def test_v2_resource_inventory_summary_executes_main_chain(monkeypatch):
    async def _fake_inventory():
        return (
            {
                "summary": {
                    "vm_count": 42,
                    "host_count": 7,
                    "cluster_count": 2,
                    "powered_off_vm_count": 1,
                    "unhealthy_host_count": 0,
                }
            },
            None,
        )

    monkeypatch.setattr(_chat_v2_module, "_query_vcenter_prod_inventory", _fake_inventory)

    data = _chat_v2("vcenter生产环境有多少虚拟机", session_id="reg-rq-1")

    chosen = (data["intent_recovery"] or {}).get("chosen_intent") or {}
    assert chosen["intent_code"] == "resource.vcenter.inventory_summary"
    assert (data["execution_intent"] or {}).get("mode") == "read"
    assert "VM总数：42" in data["assistant_message"]
    assert "主机数量：7" in data["assistant_message"]
    assert data["tool_traces"][0]["tool_name"] == "vmware.get_vcenter_inventory"
    assert any(step["stage"] == "tool_done" for step in data["analysis_steps"])


def test_v2_resource_inventory_summary_synonym_query(monkeypatch):
    async def _fake_inventory():
        return (
            {
                "summary": {
                    "vm_count": 20,
                    "host_count": 5,
                    "cluster_count": 1,
                    "powered_off_vm_count": 0,
                    "unhealthy_host_count": 1,
                }
            },
            None,
        )

    monkeypatch.setattr(_chat_v2_module, "_query_vcenter_prod_inventory", _fake_inventory)

    data = _chat_v2("查一下生产环境主机数量", session_id="reg-rq-2")

    chosen = (data["intent_recovery"] or {}).get("chosen_intent") or {}
    assert chosen["intent_code"] == "resource.vcenter.inventory_summary"
    assert "主机数量：5" in data["assistant_message"]
    assert "非健康主机数量：1" in data["assistant_message"]


def test_v2_generic_ops_qa_executes_main_chain(monkeypatch):
    async def _fake_knowledge(_message: str):
        return (
            [
                {
                    "id": "kb-vmotion",
                    "title": "vMotion 风险控制",
                    "summary": "迁移前核对网络一致性与宿主机余量。",
                    "score": 2.0,
                }
            ],
            ["vMotion", "热迁移", "虚拟机"],
        )

    monkeypatch.setattr(_chat_v2_module, "_knowledge_search_for_ops_qa", _fake_knowledge)

    data = _chat_v2("虚拟机热迁移是否会丢包", session_id="reg-gqa-1")

    chosen = (data["intent_recovery"] or {}).get("chosen_intent") or {}
    assert chosen["intent_code"] == "generic_ops_qa"
    assert (data["execution_intent"] or {}).get("mode") == "read"
    assert "结论：" in data["assistant_message"]
    assert "原理：" in data["assistant_message"]
    assert "建议：" in data["assistant_message"]
    assert "验证步骤：" in data["assistant_message"]
    assert "回退建议：" in data["assistant_message"]
    assert data["tool_traces"][0]["tool_name"] == "knowledge.search"
    assert "kb-vmotion" in data["evidence_refs"]


def test_v2_generic_ops_qa_k8s_question_routes_correctly(monkeypatch):
    async def _fake_knowledge(_message: str):
        return (
            [
                {
                    "id": "kb-k8s-restart",
                    "title": "Deployment 重启风险",
                    "summary": "单副本与探针不足时可能出现业务抖动。",
                    "score": 1.8,
                }
            ],
            ["deployment", "Kubernetes", "重启"],
        )

    monkeypatch.setattr(_chat_v2_module, "_knowledge_search_for_ops_qa", _fake_knowledge)

    data = _chat_v2("K8s deployment 重启会影响业务吗", session_id="reg-gqa-2")

    chosen = (data["intent_recovery"] or {}).get("chosen_intent") or {}
    assert chosen["intent_code"] == "generic_ops_qa"
    assert "业务抖动风险" in data["assistant_message"] or "影响" in data["assistant_message"]
    assert "验证步骤：" in data["assistant_message"]
    assert data["tool_traces"][0]["output_summary"] == "hits=1"


def test_v2_vm_export_executes_main_chain(monkeypatch):
    async def _fake_export(_session_id: str | None, _requested_columns: list[str] | None):
        return (
            {
                "export_id": "exp-1",
                "file_name": "vm-list.csv",
                "download_url": "http://127.0.0.1:8000/api/v1/chat/exports/exp-1/download",
                "expires_at": "2026-04-22T12:00:00+00:00",
                "file_size_bytes": 1024,
                "mime_type": "text/csv; charset=utf-8",
                "export_columns": ["name", "ip_address", "host_name"],
                "ignored_columns": [],
            },
            None,
        )

    monkeypatch.setattr(_chat_v2_module, "_export_vcenter_prod_vm_inventory", _fake_export)

    data = _chat_v2(
        "导出vCenter生产环境虚拟机列表，包括名称、ip地址、所在esxi主机名",
        session_id="reg-exp-1",
    )

    chosen = (data["intent_recovery"] or {}).get("chosen_intent") or {}
    assert chosen["intent_code"] == "resource.vcenter.vm_export"
    assert "已触发 vCenter 生产环境" in data["assistant_message"]
    assert data["tool_traces"][0]["tool_name"] == "vmware.export_vcenter_vm_list"
    assert data["export_file"]["download_url"].endswith("/api/v1/chat/exports/exp-1/download")
    assert data["export_columns"] == ["name", "ip_address", "host_name"]
