import os
import tempfile

from conftest import load_service_app
from fastapi.testclient import TestClient

_TMP = tempfile.TemporaryDirectory()
os.environ["MEMORY_SQLITE_PATH"] = os.path.join(_TMP.name, "memory.db")
os.environ.pop("MEMORY_POSTGRES_DSN", None)
os.environ.pop("ORCHESTRATOR_POSTGRES_DSN", None)
os.environ["NEO4J_URI"] = "bolt://127.0.0.1:1"

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "memory-service")
app = load_service_app(SERVICE_DIR)
client = TestClient(app)


def _incident_payload(root_cause: str = "vSAN frontend write latency abnormal") -> dict:
    return {
        "request_id": "req-memory-test-1",
        "tenant_id": "default",
        "user_id": "ops-user",
        "session_id": "INC-MEM-1",
        "source": "diagnosis_agent",
        "input_type": "incident_summary",
        "content": {
            "incident_id": "INC-MEM-1",
            "severity": "P2",
            "resource_type": "vmware.vm",
            "resource_id": "vm-123",
            "resource_name": "app-prod-01",
            "symptom": "VM response is slow and application access times out",
            "evidence": ["vSAN frontend write latency over 80ms"],
            "root_cause": root_cause,
            "actions": ["check vSAN disk group health"],
            "result": "resolved",
        },
    }


def test_health_uses_sqlite_fallback_and_graph_degraded():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["storage_backend"] == "sqlite"
    assert data["graph_backend"] == "degraded"


def test_policy_blocks_secret_memory():
    resp = client.post(
        "/api/v1/memories",
        json={
            "tenant_id": "default",
            "memory_type": "knowledge_memory",
            "title": "secret",
            "summary": "password=abc123 should never be stored",
            "content": {"password": "abc123"},
            "source": "test",
            "confidence": 0.9,
        },
    )
    body = resp.json()
    assert body["success"] is False
    assert "sensitive" in body["error"]


def test_incident_analyze_writes_and_searches_memory():
    resp = client.post("/api/v1/memory-agent/analyze", json=_incident_payload())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["should_write_memory"] is True
    assert len(data["memory_items"]) == 1
    memory = data["memory_items"][0]
    assert memory["memory_type"] == "vmware_incident_memory"
    assert memory["graph_sync_status"] == "degraded"

    search = client.post(
        "/api/v1/memories/search",
        json={
            "tenant_id": "default",
            "query": "vSAN latency app-prod-01",
            "filters": {"memory_type": "vmware_incident_memory", "status": "active", "tags": ["vsan"]},
            "top_k": 5,
        },
    )
    hits = search.json()["data"]["hits"]
    assert hits
    assert hits[0]["memory"]["id"] == memory["id"]


def test_resource_dimension_query_and_merge():
    first = client.post("/api/v1/memory-agent/analyze", json=_incident_payload("vSAN disk group degraded")).json()["data"]["memory_items"][0]
    second = client.post("/api/v1/memory-agent/analyze", json=_incident_payload("vSAN disk group degraded")).json()["data"]["memory_items"][0]

    resource = client.get("/api/v1/resources/vm/vm-123/memories?tenant_id=default")
    assert resource.json()["data"]["total"] >= 2

    merged = client.post(
        f"/api/v1/memories/{second['id']}/merge",
        json={
            "target_memory_id": first["id"],
            "merge_reason": "duplicate incident",
            "merge_strategy": "mark_duplicate",
        },
    )
    assert merged.json()["success"] is True
    duplicate = client.get(f"/api/v1/memories/{second['id']}").json()["data"]
    assert duplicate["status"] == "duplicate"


def test_sop_candidate_lifecycle():
    created = client.post(
        "/api/v1/sop-candidates",
        json={
            "tenant_id": "default",
            "title": "Handle recurring vSAN latency",
            "summary": "Check vSAN frontend latency and disk group health first.",
            "source_memory_ids": ["mem-a", "mem-b"],
            "recommended_steps": ["Check vSAN latency", "Check disk group health"],
        },
    ).json()["data"]
    assert created["status"] == "candidate"

    promoted = client.post(f"/api/v1/sop-candidates/{created['id']}/promote").json()["data"]
    assert promoted["status"] == "promoted"

