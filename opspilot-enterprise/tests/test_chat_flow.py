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


def test_fallback_resource_query_returns_vm_count(monkeypatch):
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
            return _FakeResp({"success": True, "data": {"summary": {"vm_count": 12}}})

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "ResourceFallback"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少虚拟机")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "当前共有 12 台虚拟机" in msg["content"]
    assert "conn-vcenter-prod" in msg["content"]


def test_fallback_resource_query_bypasses_orchestrator(monkeypatch):
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
    _, msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少虚拟机")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "当前共有 99 台虚拟机" in msg["content"]
    assert "VM总数：99" in msg["content"]
    assert "主机数量：8" in msg["content"]


def test_fallback_host_count_query_bypasses_orchestrator(monkeypatch):
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
            raise httpx.ConnectError("orchestrator should not be called")

        async def get(self, *args, **kwargs):
            return _FakeResp(
                {
                    "success": True,
                    "data": {
                        "summary": {
                            "vm_count": 99,
                            "host_count": 8,
                            "cluster_count": 3,
                        }
                    },
                }
            )

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "HostCount"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少esxi主机")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "当前共有 8 台 ESXi 主机" in msg["content"]
    assert "主机数量：8" in msg["content"]


def test_vmware_resource_counts_include_datastore_and_cluster(monkeypatch):
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
            raise httpx.ConnectError("orchestrator should not be called")

        async def get(self, *args, **kwargs):
            return _FakeResp(
                {
                    "success": True,
                    "data": {
                        "summary": {"vm_count": 99, "host_count": 8, "cluster_count": 3, "datastore_count": 5},
                        "datastores": [{"id": "ds-1", "name": "vsan-a"} for _ in range(5)],
                        "clusters": [{"cluster_id": "c-1", "name": "prod-a"} for _ in range(3)],
                    },
                }
            )

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "Counts"}).json()["data"]
    sid = sess["id"]
    _, ds_msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少datastore")
    _, cluster_msg = _post_message_and_wait(client, sid, "vcenter生产环境有多少集群")
    assert ds_msg["agent_name"] == "ResourceQueryAgent"
    assert "当前共有 5 个 Datastore" in ds_msg["content"]
    assert "当前共有 3 个集群" in cluster_msg["content"]


def test_vmware_conditional_queries_use_inventory_filters(monkeypatch):
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
            raise httpx.ConnectError("orchestrator should not be called")

        async def get(self, *args, **kwargs):
            return _FakeResp(
                {
                    "success": True,
                    "data": {
                        "summary": {"vm_count": 3, "host_count": 1, "cluster_count": 1, "datastore_count": 2},
                        "virtual_machines": [
                            {"vm_id": "vm-1", "name": "app-01", "power_state": "poweredOn"},
                            {"vm_id": "vm-2", "name": "db-01", "power_state": "poweredOff"},
                            {"vm_id": "vm-3", "name": "db-02", "power_state": "poweredOff"},
                        ],
                        "datastores": [
                            {"id": "ds-1", "name": "vsan-a", "type": "vSAN", "capacity_gb": 100, "free_gb": 10},
                            {"id": "ds-2", "name": "nfs-a", "type": "NFS", "capacity_gb": 100, "free_gb": 60},
                        ],
                    },
                }
            )

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "Filters"}).json()["data"]
    sid = sess["id"]
    _, vm_msg = _post_message_and_wait(client, sid, "生产环境关机的虚拟机有哪些")
    _, ds_msg = _post_message_and_wait(client, sid, "容量小于20%的datastore")
    assert "匹配数量：2" in vm_msg["content"]
    assert "db-01" in vm_msg["content"]
    assert "app-01" not in vm_msg["content"]
    assert "匹配数量：1" in ds_msg["content"]
    assert "vsan-a" in ds_msg["content"]
    assert "nfs-a" not in ds_msg["content"]


def test_vmware_write_intent_is_blocked(monkeypatch):
    client = _get_client()
    import app.routers.chat as chat_router

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise AssertionError("write intent must not call orchestrator or tools")

        async def get(self, *args, **kwargs):
            raise AssertionError("write intent must not query inventory before approval")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "WriteBlock"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "关闭vcenter生产环境虚拟机 Test-VM")
    assert msg["agent_name"] == "ChangeGuardAgent"
    assert "默认拦截执行类操作" in msg["content"]
    assert msg["approval_card"]["status"] == "required"


def test_vmware_host_metric_and_relationship_queries(monkeypatch):
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
            raise AssertionError("metric intent must not call orchestrator")

        async def get(self, url, *args, **kwargs):
            assert "resources/vcenter/inventory" in str(url)
            return _FakeResp(
                {
                    "success": True,
                    "data": {
                        "summary": {"host_count": 1, "datastore_count": 1},
                        "hosts": [
                            {
                                "host_id": "host-1",
                                "name": "esx01.lab.local",
                                "cpu_mhz": 100000,
                                "cpu_usage_mhz": 45000,
                                "memory_mb": 102400,
                                "memory_usage_mb": 51200,
                                "vm_count": 2,
                                "overall_status": "green",
                            }
                        ],
                        "datastores": [
                            {
                                "id": "ds-1",
                                "name": "vsanDatastore",
                                "type": "vsan",
                                "capacity_gb": 1000,
                                "free_gb": 250,
                                "host_ids": ["host-1"],
                                "host_names": ["esx01.lab.local"],
                            }
                        ],
                        "virtual_machines": [],
                        "clusters": [],
                    },
                }
            )

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "Metrics"}).json()["data"]
    sid = sess["id"]
    _, metric_msg = _post_message_and_wait(client, sid, "esx01 的 CPU 使用率是多少")
    _, relation_msg = _post_message_and_wait(client, sid, "esx01 关联哪些 datastore，剩余容量多少")
    assert metric_msg["agent_name"] == "ResourceQueryAgent"
    assert "CPU 使用率" in metric_msg["content"]
    assert "45.0%" in metric_msg["content"] or "45%" in metric_msg["content"]
    assert "数据来源：inventory" in metric_msg["content"]
    assert "vsanDatastore" in relation_msg["content"]
    assert "剩余=250GB/25.0%" in relation_msg["content"] or "剩余=250GB/25%" in relation_msg["content"]


def test_vmware_historical_metric_prefers_prometheus(monkeypatch):
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
            raise AssertionError("prometheus success should avoid vcenter metric fallback")

        async def get(self, url, *args, **kwargs):
            url_s = str(url)
            if "resources/vcenter/inventory" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "summary": {"host_count": 1},
                            "hosts": [{"host_id": "host-1", "name": "esx01.lab.local", "cpu_mhz": 100000, "cpu_usage_mhz": 30000}],
                            "datastores": [],
                            "virtual_machines": [],
                            "clusters": [],
                        },
                    }
                )
            if "query_range" in url_s:
                return _FakeResp(
                    {
                        "status": "success",
                        "data": {
                            "result": [
                                {
                                    "metric": {"host_id": "host-1"},
                                    "values": [[1700000000, "10"], [1700000300, "20"]],
                                }
                            ]
                        },
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "PromMetrics"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "过去1小时 esx01 CPU 平均使用率")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "15.0%" in msg["content"] or "15%" in msg["content"]
    assert "数据来源：prometheus" in msg["content"]
    assert msg["tool_traces"][0]["tool_name"] == "prometheus.query_range"


def test_vmware_host_cpu_memory_overview_returns_metric_result(monkeypatch):
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
            raise AssertionError("metric overview must not call orchestrator")

        async def get(self, url, *args, **kwargs):
            url_s = str(url)
            if "resources/vcenter/inventory" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "summary": {"host_count": 2},
                            "hosts": [
                                {
                                    "host_id": "host-1",
                                    "name": "esx01.lab.local",
                                    "cpu_mhz": 100000,
                                    "cpu_usage_mhz": 45000,
                                    "memory_mb": 102400,
                                    "memory_usage_mb": 51200,
                                },
                                {
                                    "host_id": "host-2",
                                    "name": "esx02.lab.local",
                                    "cpu_mhz": 100000,
                                    "cpu_usage_mhz": 92000,
                                    "memory_mb": 102400,
                                    "memory_usage_mb": 88064,
                                },
                            ],
                            "datastores": [],
                            "virtual_machines": [],
                            "clusters": [],
                        },
                    }
                )
            if "query_range" in url_s:
                return _FakeResp({"status": "success", "data": {"result": []}})
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sess = client.post("/api/v1/chat/sessions", json={"title": "HostMetricOverview"}).json()["data"]
    sid = sess["id"]
    _, msg = _post_message_and_wait(client, sid, "过去1小时，esxi主机的cpu使用率和内存使用率")
    metric_result = msg.get("metric_result") or {}

    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "过去 1 小时生产环境 2 台 ESXi 主机" in msg["content"]
    assert "数据来源" in msg["content"]
    assert metric_result["scope"] == "esxi_hosts"
    assert metric_result["window"] == "1h"
    assert metric_result["source"] == "vcenter_inventory"
    assert len(metric_result["series"]) > 0
    assert {item["name"] for item in metric_result["metrics"]} == {"cpu_usage_percent", "memory_usage_percent"}
    assert metric_result["top_hosts"][0]["name"] == "esx02.lab.local"
    assert "查看 esx02.lab.local 上的虚拟机" in metric_result["next_actions"]
    assert metric_result["next_action_items"][0]["prompt"] == "查看生产环境 esx02.lab.local 上的虚拟机"
    assert msg["recommended_actions"] == metric_result["next_actions"]
    assert msg["tool_traces"][0]["tool_name"] == "vmware.get_vcenter_inventory"


def test_vmware_host_cpu_memory_overview_normal_actions(monkeypatch):
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
            raise AssertionError("metric overview must not call orchestrator")

        async def get(self, url, *args, **kwargs):
            url_s = str(url)
            if "resources/vcenter/inventory" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "summary": {"host_count": 1},
                            "hosts": [
                                {
                                    "host_id": "host-1",
                                    "name": "esx01.lab.local",
                                    "cpu_mhz": 100000,
                                    "cpu_usage_mhz": 30000,
                                    "memory_mb": 102400,
                                    "memory_usage_mb": 40960,
                                }
                            ],
                            "datastores": [],
                            "virtual_machines": [],
                            "clusters": [],
                        },
                    }
                )
            if "query_range" in url_s:
                return _FakeResp({"status": "success", "data": {"result": []}})
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sid = client.post("/api/v1/chat/sessions", json={"title": "NormalActions"}).json()["data"]["id"]
    _, msg = _post_message_and_wait(client, sid, "过去1小时，esxi主机的cpu使用率和内存使用率")
    actions = msg["metric_result"]["next_action_items"]
    assert [item["label"] for item in actions] == ["查看最近vCenter告警和事件", "导出ESXi资源使用率报表"]
    assert actions[0]["prompt"] == "查看生产环境最近24小时 vCenter 告警和事件"
    assert actions[1]["prompt"] == "导出生产环境ESXi主机过去1小时CPU和内存使用率报表"


def test_vmware_metric_followup_alert_events(monkeypatch):
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

        async def get(self, *args, **kwargs):
            raise AssertionError("alert/event follow-up should not query inventory for global scope")

        async def post(self, url, *args, **kwargs):
            url_s = str(url)
            if "vmware.query_alerts" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "alerts": [
                                {
                                    "object_id": "host-1",
                                    "object_name": "esx01.lab.local",
                                    "severity": "warning",
                                    "summary": "Host CPU warning",
                                }
                            ]
                        },
                    }
                )
            if "vmware.query_events" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "events": [
                                {
                                    "event_type": "HostConnectionStateChangedEvent",
                                    "level": "info",
                                    "message": "Host event",
                                    "created_time": "2026-04-28T01:00:00Z",
                                }
                            ]
                        },
                    }
                )
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sid = client.post("/api/v1/chat/sessions", json={"title": "Events"}).json()["data"]["id"]
    _, msg = _post_message_and_wait(client, sid, "查看生产环境最近24小时 vCenter 告警和事件")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert "告警和事件" in msg["content"]
    assert "Host CPU warning" in msg["content"]
    assert "Host event" in msg["content"]
    assert [trace["tool_name"] for trace in msg["tool_traces"]] == ["vmware.query_alerts", "vmware.query_events"]


def test_vmware_metric_followup_exports_report_from_cached_metric_result(monkeypatch):
    client = _get_client()
    import app.routers.chat as chat_router

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            raise AssertionError("cached metric report export should not query inventory")

        async def post(self, *args, **kwargs):
            raise AssertionError("cached metric report export should not call orchestrator")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sid = client.post("/api/v1/chat/sessions", json={"title": "MetricReport"}).json()["data"]["id"]
    chat_router._messages[sid].append(
        {
            "id": "cached-assistant",
            "session_id": sid,
            "role": "assistant",
            "content": "cached",
            "timestamp": "2026-04-28T00:00:00Z",
            "status": "completed",
            "metric_result": {
                "scope": "esxi_hosts",
                "window": "1h",
                "source": "prometheus",
                "series": [],
                "summary_stats": {"host_count": 1},
                "host_series": [
                    {
                        "host_id": "host-1",
                        "name": "esx01.lab.local",
                        "cpu_current": 30,
                        "cpu_avg": 25,
                        "cpu_peak": 40,
                        "memory_current": 50,
                        "memory_avg": 45,
                        "memory_peak": 60,
                    }
                ],
            },
        }
    )

    _, msg = _post_message_and_wait(client, sid, "导出生产环境ESXi主机过去1小时CPU和内存使用率报表")
    assert msg["agent_name"] == "ResourceQueryAgent"
    assert msg["export_file"]["file_name"].endswith(".csv")
    export_id = msg["export_file"]["export_id"]
    download = client.get(f"/api/v1/chat/exports/{export_id}/download")
    assert download.status_code == 200
    assert "esx01.lab.local" in download.text
    assert "cpu_peak_percent" in download.text


def test_vmware_metric_followup_host_diagnosis_includes_events(monkeypatch):
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

        async def get(self, url, *args, **kwargs):
            if "resources/vcenter/inventory" in str(url):
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "summary": {"host_count": 1},
                            "hosts": [
                                {
                                    "host_id": "host-1",
                                    "name": "esx01.lab.local",
                                    "overall_status": "green",
                                    "connection_state": "connected",
                                    "cpu_mhz": 100000,
                                    "cpu_usage_mhz": 35000,
                                    "memory_mb": 102400,
                                    "memory_usage_mb": 51200,
                                    "vm_count": 3,
                                }
                            ],
                            "virtual_machines": [],
                            "datastores": [],
                            "clusters": [],
                        },
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

        async def post(self, url, *args, **kwargs):
            url_s = str(url)
            if "vmware.query_alerts" in url_s:
                return _FakeResp(
                    {
                        "success": True,
                        "data": {
                            "alerts": [
                                {
                                    "object_id": "host-1",
                                    "object_name": "esx01.lab.local",
                                    "severity": "warning",
                                    "summary": "Memory pressure warning",
                                }
                            ]
                        },
                    }
                )
            if "vmware.query_events" in url_s:
                return _FakeResp({"success": True, "data": {"events": [{"message": "Host reconnect event", "level": "info"}]}})
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr(chat_router.httpx, "AsyncClient", _FakeAsyncClient)

    sid = client.post("/api/v1/chat/sessions", json={"title": "HostDiag"}).json()["data"]["id"]
    _, msg = _post_message_and_wait(client, sid, "诊断生产环境 esx01.lab.local 健康状态")
    assert msg["agent_name"] == "RCAAgent"
    assert msg["diagnosis_id"]
    assert "最近告警：1 条" in msg["content"]
    assert "Host reconnect event" in msg["content"]
    assert "ev-fallback-host-alert-events" in msg["evidence_refs"]


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
