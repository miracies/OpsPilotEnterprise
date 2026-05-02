"""Smoke tests for Evidence Aggregator."""
import os
import sys
from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "evidence-aggregator")
_app = load_service_app(SERVICE_DIR)
AGGREGATOR_MAIN = sys.modules["app.main"]
client = TestClient(_app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_aggregate():
    resp = client.post("/api/v1/evidence/aggregate", json={
        "incident_id": "inc-001",
        "source_refs": ["host-33", "vm-201"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_get_evidence():
    resp = client.get("/api/v1/evidence/evd-test-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_vm_diagnosis_bundle_becomes_evidence(monkeypatch):
    aggregator_main = AGGREGATOR_MAIN

    async def _fake_get_incident(_incident_id):
        return {
            "id": "inc-vm-red",
            "title": "VM overallStatus red",
            "summary": "vCenter reports VM overallStatus red",
            "severity": "critical",
            "source_type": "vmware_non_green",
            "affected_objects": [{"object_id": "vm-005", "object_type": "VirtualMachine", "object_name": "db-server-01"}],
            "details": {},
        }

    async def _fake_match_alert_knowledge(_incident, _alert_context):
        return {
            "required_evidence_types": ["detail", "alert", "event", "metric", "topology"],
            "matches": [
                {
                    "item": {
                        "id": "AK-VMWARE-VM-OVERALL-STATUS-RED",
                        "alert_name": "VM overallStatus red",
                        "tags": ["vmware", "vm_level"],
                    },
                    "why_selected": "exact alert name matched",
                    "relevance_score": 0.95,
                }
            ],
            "safe_actions": ["vmware.collect_vm_diagnosis_bundle"],
            "approval_actions": ["vmware.vm_guest_restart"],
        }

    async def _fake_invoke_tool(tool_name, _input_payload, timeout_sec=12.0):
        if tool_name == "vmware.collect_vm_diagnosis_bundle":
            return {
                "basic_status": {
                    "overall_status": "red",
                    "connection_state": "connected",
                    "power_state": "poweredOn",
                    "guest_heartbeat_status": "gray",
                    "tools_status": "toolsOk",
                    "host_name": "esxi-node03.corp.local",
                },
                "triggered_alarms": [{"alarm_name": "VM overallStatus red", "status": "red", "acknowledged": False}],
                "config_issues": [{"fault_type": "SnapshotConsolidationNeeded", "message": "Consolidation needed"}],
                "recent_events": [{"event_type": "VmReconfiguredEvent", "message": "VM configuration updated"}],
                "snapshot_status": {"snapshot_count": 1, "consolidation_needed": True},
                "dependency_status": {"host": {"name": "esxi-node03.corp.local"}, "datastores": [{"name": "vsanDatastore-prod-a"}], "networks": []},
                "performance_metrics": {"vm.cpu_usage_percent": [{"timestamp": "2026-05-01T00:00:00Z", "value": 91.0}]},
            }
        if tool_name == "vmware.get_vm_detail":
            return {"overall_status": "red", "connection_state": "connected", "power_state": "poweredOn"}
        if tool_name == "vmware.query_events":
            return {"events": []}
        if tool_name == "vmware.query_metrics":
            return {"metric": "cpu_usage_percent", "series": [{"timestamp": "2026-05-01T00:00:00Z", "value": 91.0}]}
        if tool_name == "vmware.query_alerts":
            return {"alerts": []}
        if tool_name == "vmware.get_vcenter_inventory":
            return {"summary": {"cluster_count": 1, "host_count": 1, "vm_count": 1}}
        return {}

    async def _fake_search_kb(_query_text):
        return []

    async def _fake_collect_optional(_object_id, _summary, _corr):
        return [], None

    async def _fake_collect_logs(**_kwargs):
        ev = aggregator_main._make_ev(
            source="log-gateway.opensearch",
            source_type="log",
            object_type="VirtualMachine",
            object_id="vm-005",
            summary="vm_related_logs: vpxd alarm state changed for VM overallStatus red",
            confidence=0.72,
            raw_ref="log://opensearch:idx:doc",
            correlation_key="incident:inc-vm-red",
            external_links=[{"provider": "opensearch", "title": "OpenSearch Dashboards", "url": "http://logs/q"}],
        )
        return [ev], None

    monkeypatch.setattr(aggregator_main, "_get_incident", _fake_get_incident)
    monkeypatch.setattr(aggregator_main, "_match_alert_knowledge", _fake_match_alert_knowledge)
    monkeypatch.setattr(aggregator_main, "_invoke_tool", _fake_invoke_tool)
    monkeypatch.setattr(aggregator_main, "_search_kb", _fake_search_kb)
    monkeypatch.setattr(aggregator_main, "_collect_graylog_evidence", _fake_collect_optional)
    monkeypatch.setattr(aggregator_main, "_collect_opennms_evidence", _fake_collect_optional)
    monkeypatch.setattr(aggregator_main, "_collect_log_gateway_evidence", _fake_collect_logs)

    resp = client.post("/api/v1/evidence/aggregate", json={"incident_id": "inc-vm-red", "source_refs": ["vm-005"]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "AK-VMWARE-VM-OVERALL-STATUS-RED" in data["alert_knowledge_ids"]
    assert {"detail", "alert", "event", "metric", "topology"} <= set(data["present_evidence_types"])
    assert "log" in data["present_evidence_types"]
    assert data["missing_critical_evidence"] == []
    assert "vmware.collect_vm_diagnosis_bundle" in data["safe_actions"]
    log_items = [ev for ev in data["evidences"] if ev["source_type"] == "log"]
    assert log_items[0]["raw_ref"].startswith("log://")
    assert log_items[0]["external_links"][0]["provider"] == "opensearch"
