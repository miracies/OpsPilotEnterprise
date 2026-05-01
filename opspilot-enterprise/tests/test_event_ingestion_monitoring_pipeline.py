import asyncio
import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import load_service_app

SERVICE_DIR = Path(__file__).resolve().parents[1] / "services" / "event-ingestion-service"


def _load_event_service(tmp_path, monkeypatch):
    db_path = tmp_path / "events.db"
    monkeypatch.setenv("EVENTS_DB_PATH", str(db_path))
    monkeypatch.setenv("MONITOR_ENABLED_ON_START", "false")
    app = load_service_app(str(SERVICE_DIR))
    event_main = importlib.import_module("app.main")
    event_main._init_db()
    client = TestClient(app)
    return client, event_main


def _inventory_with_vm(power_state: str, name: str = "app-01", vm_id: str = "vm-01"):
    return {
        "generated_at": "2026-04-24T08:00:00+00:00",
        "hosts": [],
        "clusters": [],
        "virtual_machines": [{"vm_id": vm_id, "name": name, "power_state": power_state}],
        "datastores": [],
    }


def _empty_vcenter_collectors(tool_name: str):
    if tool_name == "vmware.query_alerts":
        return {"alerts": []}
    if tool_name == "vmware.query_events":
        return {"events": []}
    if tool_name == "k8s.get_workload_status":
        return {"nodes": [], "pods": [], "deployments": []}
    return None


def test_monitoring_cycle_projects_vcenter_host_sync_event(tmp_path, monkeypatch):
    client, event_main = _load_event_service(tmp_path, monkeypatch)

    async def fake_invoke_tool(tool_name: str, payload: dict, dry_run: bool = False):
        if tool_name == "vmware.get_vcenter_inventory":
            return {
                "generated_at": "2026-04-24T08:00:00+00:00",
                "hosts": [
                    {
                        "host_id": "host-01",
                        "name": "esx01.vstecs.lab",
                        "cpu_mhz": 10000,
                        "cpu_usage_mhz": 2000,
                        "memory_mb": 65536,
                        "memory_usage_mb": 20480,
                        "vm_count": 24,
                        "connection_state": "connected",
                        "power_state": "poweredOn",
                        "overall_status": "green",
                    }
                ],
                "clusters": [],
                "virtual_machines": [],
                "datastores": [],
            }
        if tool_name == "vmware.query_alerts":
            return {"alerts": []}
        if tool_name == "vmware.query_events":
            return {
                "events": [
                    {
                        "event_id": "evt-1",
                        "event_type": "HostConnectionLostEvent",
                        "level": "warning",
                        "message": "cannot synchronize host esx01.vstecs.lab",
                        "created_time": "2026-04-24T08:01:00+00:00",
                    }
                ]
            }
        if tool_name == "vmware.get_host_detail":
            return {
                "host_id": "host-01",
                "name": "esx01.vstecs.lab",
                "connection_state": "disconnected",
                "overall_status": "yellow",
                "cpu_usage_percent": 20.0,
                "memory_usage_percent": 31.25,
            }
        if tool_name == "k8s.get_workload_status":
            return {"nodes": [], "pods": [], "deployments": []}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(event_main, "_invoke_tool", fake_invoke_tool)

    asyncio.run(event_main._monitoring_cycle())

    resp = client.get("/api/v1/incidents")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    incidents = payload["data"]["incidents"]
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["affected_objects"][0]["object_name"] == "esx01.vstecs.lab"
    assert incident["correlation_key"] == f"{event_main.VCENTER_CONN_ID}:HostSystem:host-01:vc-host-sync-failed"
    assert "event:evt-1" in incident["source_event_refs"]
    assert incident["validation_summary"]["status"] == "active"


def test_monitoring_status_exposes_collectors_and_stats(tmp_path, monkeypatch):
    client, event_main = _load_event_service(tmp_path, monkeypatch)

    async def fake_invoke_tool(tool_name: str, payload: dict, dry_run: bool = False):
        if tool_name == "vmware.get_vcenter_inventory":
            return {
                "generated_at": "2026-04-24T08:00:00+00:00",
                "hosts": [],
                "clusters": [],
                "virtual_machines": [],
                "datastores": [],
            }
        if tool_name == "vmware.query_alerts":
            return {"alerts": []}
        if tool_name == "k8s.get_workload_status":
            return {"nodes": [], "pods": [], "deployments": []}
        if tool_name == "vmware.query_events":
            return {"events": []}
        raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(event_main, "_invoke_tool", fake_invoke_tool)

    asyncio.run(event_main._monitoring_cycle())

    resp = client.get("/api/v1/monitoring/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert "collectors" in data
    assert "source_stats" in data
    collector_names = {item["collector_name"] for item in data["collectors"]}
    assert {"vcenter_inventory", "vcenter_alerts", "vcenter_key_events", "k8s_workload"}.issubset(collector_names)
    assert "projector" in data["source_stats"]["last_cycle"]


def test_incident_list_defaults_to_lightweight_summary(tmp_path, monkeypatch):
    client, event_main = _load_event_service(tmp_path, monkeypatch)
    incident = event_main._upsert_incident_from_event(
        event_main.IngestEventBody(
            source="vmware-event",
            source_type="vmware_key_event",
            object_type="HostSystem",
            object_id="host-heavy",
            object_name="esx-heavy.lab",
            severity="high",
            summary="Host esx-heavy.lab test incident",
            rule_id="vc-host-test",
            correlation_key=f"{event_main.VCENTER_CONN_ID}:HostSystem:host-heavy:vc-host-test",
            evidence_refs=["event:evt-heavy"],
        )
    )
    row = event_main._query_one("SELECT details_json FROM incidents WHERE id=?", (incident["id"],))
    details = event_main.json.loads(row["details_json"])
    details["analysis"] = {
        "status": "completed",
        "round": 2,
        "max_rounds": 5,
        "analysis_process": [{"round": 1, "stage": "evidence_collection", "finding": "heavy", "decision": "continue", "timestamp": "2026-04-24T08:00:00+00:00", "status": "success"}],
        "final_conclusion": "heavy detail",
    }
    details["memory_context"] = {"similar_incidents": [{"large": "x" * 1000}]}
    event_main._exec("UPDATE incidents SET details_json=? WHERE id=?", (event_main.json.dumps(details), incident["id"]))

    list_resp = client.get("/api/v1/incidents")
    detail_resp = client.get(f"/api/v1/incidents/{incident['id']}")

    summary = list_resp.json()["data"]["incidents"][0]
    detail = detail_resp.json()["data"]
    assert list_resp.json()["data"]["view"] == "summary"
    assert summary["analysis"]["analysis_process"] == []
    assert "details" not in summary
    assert summary["source_event_refs"] == ["event:evt-heavy"]
    assert detail["analysis"]["analysis_process"][0]["finding"] == "heavy"
    assert detail["details"]["memory_context"]["similar_incidents"][0]["large"].startswith("x")


def test_incident_list_supports_detail_view_and_limit(tmp_path, monkeypatch):
    client, event_main = _load_event_service(tmp_path, monkeypatch)
    for idx in range(3):
        event_main._upsert_incident_from_event(
            event_main.IngestEventBody(
                source="vmware-event",
                source_type="vmware_key_event",
                object_type="HostSystem",
                object_id=f"host-{idx}",
                severity="high",
                summary=f"Host {idx} test incident",
                correlation_key=f"test-limit-{idx}",
            )
        )

    resp = client.get("/api/v1/incidents?view=detail&limit=2")

    data = resp.json()["data"]
    assert data["view"] == "detail"
    assert data["limit"] == 2
    assert len(data["incidents"]) == 2
    assert "details" in data["incidents"][0]


def test_plain_powered_off_vm_does_not_create_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("VCENTER_POWERED_OFF_VM_INCIDENT_MODE", "expected_only")
    monkeypatch.delenv("VCENTER_EXPECTED_RUNNING_VM_PATTERNS", raising=False)
    client, event_main = _load_event_service(tmp_path, monkeypatch)

    async def fake_invoke_tool(tool_name: str, payload: dict, dry_run: bool = False):
        if tool_name == "vmware.get_vcenter_inventory":
            return _inventory_with_vm("poweredOff", name="ESX01-ZuwL", vm_id="vm-off-01")
        fallback = _empty_vcenter_collectors(tool_name)
        if fallback is not None:
            return fallback
        raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(event_main, "_invoke_tool", fake_invoke_tool)

    asyncio.run(event_main._monitoring_cycle())

    resp = client.get("/api/v1/incidents")
    assert resp.status_code == 200
    incidents = resp.json()["data"]["incidents"]
    assert incidents == []


def test_plain_powered_off_vm_resolves_existing_power_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("VCENTER_POWERED_OFF_VM_INCIDENT_MODE", "expected_only")
    monkeypatch.delenv("VCENTER_EXPECTED_RUNNING_VM_PATTERNS", raising=False)
    client, event_main = _load_event_service(tmp_path, monkeypatch)

    event_main._upsert_incident_from_event(
        event_main.IngestEventBody(
            source="vmware-monitor",
            source_type="vm_guest_down",
            object_type="VirtualMachine",
            object_id="vm-off-01",
            object_name="ESX01-ZuwL",
            severity="medium",
            summary="VM ESX01-ZuwL is powered off",
            rule_id="vc-vm-powered-off",
            correlation_key=f"{event_main.VCENTER_CONN_ID}:VirtualMachine:vm-off-01:vc-vm-powered-off",
        )
    )

    resolved = event_main._resolve_suppressed_vm_powered_off_incidents(
        _inventory_with_vm("poweredOff", name="ESX01-ZuwL", vm_id="vm-off-01")
    )

    assert resolved == 1
    incident = client.get("/api/v1/incidents").json()["data"]["incidents"][0]
    assert incident["status"] == "resolved"
    assert "普通 VM 关机不是故障" in incident["validation_summary"]["reason"] or incident["validation_summary"]["status"] == "recovered"


def test_expected_running_powered_off_vm_creates_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("VCENTER_POWERED_OFF_VM_INCIDENT_MODE", "expected_only")
    monkeypatch.setenv("VCENTER_EXPECTED_RUNNING_VM_PATTERNS", "critical-.*")
    client, event_main = _load_event_service(tmp_path, monkeypatch)

    async def fake_invoke_tool(tool_name: str, payload: dict, dry_run: bool = False):
        if tool_name == "vmware.get_vcenter_inventory":
            return _inventory_with_vm("poweredOff", name="critical-db-01", vm_id="vm-critical-01")
        fallback = _empty_vcenter_collectors(tool_name)
        if fallback is not None:
            return fallback
        raise AssertionError(f"unexpected tool call: {tool_name}")

    monkeypatch.setattr(event_main, "_invoke_tool", fake_invoke_tool)

    asyncio.run(event_main._monitoring_cycle())

    incidents = client.get("/api/v1/incidents").json()["data"]["incidents"]
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["status"] == "new"
    assert incident["correlation_key"] == f"{event_main.VCENTER_CONN_ID}:VirtualMachine:vm-critical-01:vc-vm-powered-off"
    assert incident["validation_summary"]["inventory"]["expected_running"] is True
    assert "确认 critical-db-01 是否应保持运行" in incident["recommended_actions"]


def test_expected_running_powered_on_vm_resolves_power_incident(tmp_path, monkeypatch):
    monkeypatch.setenv("VCENTER_POWERED_OFF_VM_INCIDENT_MODE", "expected_only")
    monkeypatch.setenv("VCENTER_EXPECTED_RUNNING_VM_PATTERNS", "critical-.*")
    client, event_main = _load_event_service(tmp_path, monkeypatch)
    inventory_off = _inventory_with_vm("poweredOff", name="critical-db-01", vm_id="vm-critical-01")
    events = event_main._normalize_inventory_events(inventory_off)

    asyncio.run(event_main._project_events(events, inventory_off, {"alerts": []}))
    resolved = event_main._resolve_suppressed_vm_powered_off_incidents(
        _inventory_with_vm("poweredOn", name="critical-db-01", vm_id="vm-critical-01")
    )

    assert resolved == 1
    incident = client.get("/api/v1/incidents").json()["data"]["incidents"][0]
    assert incident["status"] == "resolved"
    assert incident["validation_summary"]["inventory"]["power_state"] == "poweredOn"


def test_powered_off_summary_does_not_plan_vm_power_on_approval(tmp_path, monkeypatch):
    client, event_main = _load_event_service(tmp_path, monkeypatch)
    incident = event_main._upsert_incident_from_event(
        event_main.IngestEventBody(
            source="vmware-monitor",
            source_type="vm_guest_down",
            object_type="VirtualMachine",
            object_id="vm-off-01",
            object_name="ESX01-ZuwL",
            severity="medium",
            summary="VM ESX01-ZuwL is powered off",
            rule_id="vc-vm-powered-off",
            correlation_key=f"{event_main.VCENTER_CONN_ID}:VirtualMachine:vm-off-01:vc-vm-powered-off",
        )
    )
    recommendations: list[str] = []

    did_execute, logs = asyncio.run(
        event_main._maybe_auto_remediate(
            incident_id=incident["id"],
            user_mode="full_auto",
            recommendations=recommendations,
            mode="auto",
            summary="VM ESX01-ZuwL is powered off",
        )
    )

    assert did_execute is False
    assert any("未命中可执行的低风险动作" in item for item in logs)
    approvals = client.get("/api/v1/approvals?status=pending").json()["data"]["items"]
    assert approvals == []
