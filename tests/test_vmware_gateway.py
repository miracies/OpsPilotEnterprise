"""Smoke tests for VMware Skill Gateway."""
import os
from conftest import load_service_app
from fastapi.testclient import TestClient

os.environ.setdefault("VMWARE_USE_MOCK_FALLBACK", "true")

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "vmware-skill-gateway")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_capabilities():
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "tools" in data["data"]


def test_get_vcenter_inventory():
    resp = client.post("/api/v1/query/get_vcenter_inventory", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    inventory = data["data"]
    assert inventory["hosts"][0]["cpu_usage_percent"] is not None
    assert inventory["datastores"][0]["host_ids"]
    assert inventory["datastores"][0]["free_percent"] is not None


def test_query_events():
    resp = client.post("/api/v1/query/query_events", json={"object_id": "host-33", "hours": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_collect_vm_diagnosis_bundle():
    resp = client.post("/api/v1/query/collect_vm_diagnosis_bundle", json={"vm_id": "vm-005", "hours": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    bundle = data["data"]
    assert bundle["basic_status"]["overall_status"] == "red"
    assert bundle["triggered_alarms"]
    assert bundle["config_issues"]
    assert bundle["snapshot_status"]["consolidation_needed"] is True

    resp = client.post("/api/v1/invoke/vmware.collect_vm_diagnosis_bundle", json={"input": {"vm_id": "vm-005"}})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_invoke_inventory():
    resp = client.post("/api/v1/invoke/vmware.get_vcenter_inventory", json={"input": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_vmware_metrics_endpoint():
    resp = client.get("/metrics/vmware")
    assert resp.status_code == 200
    text = resp.text
    assert "opspilot_vmware_host_cpu_usage_percent" in text
    assert "opspilot_vmware_datastore_free_percent" in text
