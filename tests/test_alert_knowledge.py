"""Tests for AlertKnowledge schema and knowledge-service APIs."""
from __future__ import annotations

import os
import sys
import tempfile

import pytest
from conftest import load_service_app
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))

from opspilot_schema.knowledge import AlertKnowledge, AlertKnowledgeAutomation

os.environ["KNOWLEDGE_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="opspilot-knowledge-"), "knowledge.db")

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "knowledge-service")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)
for _module_name in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
    del sys.modules[_module_name]


def _sample_alert(alert_id: str = "AK-TEST-CPU") -> dict:
    return {
        "id": alert_id,
        "alert_name": f"Test VM CPU pressure {alert_id}",
        "vendor": "vmware",
        "domain": "virtualization",
        "category": "resource",
        "severity": "critical",
        "aliases": ["cpu pressure", "vm cpu high"],
        "symptoms": ["VM CPU is high"],
        "possible_causes": ["Guest workload spike", "CPU ready"],
        "diagnostic_steps": ["Collect VM and host CPU metrics"],
        "decision_tree": ["if ready high -> host contention"],
        "evidence_required": ["metric", "detail", "event"],
        "remediation": ["Collect evidence before migration"],
        "automation": {"safe_actions": ["collect_vm_metrics"], "approval_actions": ["vmware.vm_migrate"]},
        "source": {"type": "manual", "title": "unit test", "trust_score": 0.8},
        "status": "published",
        "version": "1.0.0",
        "trust_score": 0.8,
        "hit_count": 0,
        "case_refs": [],
        "knowledge_refs": [],
        "tags": ["vmware", "cpu"],
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }


def test_schema_rejects_missing_evidence_required():
    body = _sample_alert()
    body["evidence_required"] = []
    with pytest.raises(ValidationError):
        AlertKnowledge(**body)


def test_schema_accepts_legacy_and_structured_decision_tree():
    legacy = AlertKnowledge(**_sample_alert("AK-TEST-LEGACY"))
    assert legacy.decision_tree[0].condition == "if ready high -> host contention"

    body = _sample_alert("AK-TEST-STRUCTURED")
    body["decision_tree"] = [
        {
            "condition": "vm.cpu.ready > 5",
            "conclusion": "Host contention",
            "confidence_delta": 0.3,
            "required_evidence": ["vm.cpu.ready"],
        }
    ]
    item = AlertKnowledge(**body)
    assert item.decision_tree[0].required_evidence == ["vm.cpu.ready"]


def test_schema_rejects_risky_safe_action():
    with pytest.raises(ValidationError):
        AlertKnowledgeAutomation(safe_actions=["vmware.vm_migrate"], approval_actions=[])


def test_seeded_vmware_alerts_are_available():
    resp = client.get("/knowledge/alert-items?vendor=vmware")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 30
    categories = {item["category"] for item in data["items"]}
    assert {"resource", "ha_cluster", "vmotion_drs", "storage", "network", "vm_level"} <= categories


def test_upsert_and_duplicate_handling():
    item = _sample_alert()
    resp = client.post("/knowledge/alert-items?upsert=true", json=item)
    assert resp.status_code == 200
    assert resp.json()["data"]["created"] is True

    item["symptoms"] = ["VM CPU remains high for 5 minutes"]
    resp = client.post("/knowledge/alert-items?upsert=true", json=item)
    assert resp.status_code == 200
    assert resp.json()["data"]["created"] is False

    resp = client.post("/knowledge/alert-items?upsert=false", json=item)
    assert resp.status_code == 409


def test_alert_match_returns_missing_evidence_and_actions():
    resp = client.post(
        "/knowledge/alert-match",
        json={
            "alert_name": "Virtual machine CPU usage",
            "summary": "app-01 VM CPU usage high and CPU ready is elevated",
            "vendor": "vmware",
            "evidence_present": ["event"],
            "top_k": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["matches"]
    assert "metric" in data["missing_evidence"]
    assert data["matches"][0]["matched_fields"]
    assert data["matches"][0]["missing_critical_evidence"]
    assert data["safe_actions"]
    assert data["approval_actions"]


def test_bulk_import_dry_run_import_jobs_deprecate_feedback_and_prometheus_rule_converter():
    item = _sample_alert("AK-TEST-BULK")
    resp = client.post("/knowledge/import/validate", json={"content": __import__("json").dumps(item), "content_type": "json"})
    assert resp.status_code == 200
    assert resp.json()["data"]["valid"] is True

    resp = client.post("/knowledge/alert-items:bulk-import", json={"items": [item], "source_type": "manual", "upsert": True, "dry_run": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "validated"

    resp = client.post("/knowledge/alert-items:bulk-import", json={"items": [item], "source_type": "manual", "upsert": True})
    assert resp.status_code == 200
    job_id = resp.json()["data"]["job_id"]
    assert resp.json()["data"]["created"] + resp.json()["data"]["updated"] == 1

    resp = client.get(f"/knowledge/import-jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == job_id

    resp = client.post("/knowledge/alert-items/AK-TEST-BULK/deprecate")
    assert resp.status_code == 200
    assert resp.json()["data"]["item"]["status"] == "deprecated"

    resp = client.post(
        "/knowledge/feedback",
        json={
            "alert_knowledge_id": "AK-TEST-BULK",
            "incident_id": "INC-1",
            "match_correct": True,
            "actual_root_cause": "CPU ready",
            "missing_evidence": ["metric"],
            "accepted_actions": ["collect_vm_metrics"],
            "comment": "good match",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"].startswith("KFB-")

    rules = """
groups:
  - name: vmware
    rules:
      - alert: VMwareDatastoreAlmostFull
        expr: datastore_usage_percent > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: Datastore usage is above 85 percent
"""
    resp = client.post("/knowledge/importers/prometheus-rules", json={"content": rules, "publish": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["articles_imported"] == 1
