"""Data-driven intent regression using the shared evaluation dataset."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import load_service_app

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "data" / "intent_understanding_cases.json"
SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "langgraph-orchestrator")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)

DATASET_CASE_IDS = {
    "J001",
    "J003",
    "J005",
    "J006",
    "J007",
    "J008",
    "J009",
    "J010",
    "J012",
    "J013",
    "J014",
    "J015",
    "S010",
    "S011",
    "S013",
}


def _load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _expected_decision(case: dict) -> set[str]:
    next_step = case["expected_next_step"]
    if next_step == "clarify":
        return {"clarify_required"}
    if next_step in {"direct_answer", "diagnose"}:
        return {"recovered"}
    if next_step in {"approval", "execute"}:
        return {"recovered", "clarify_required"}
    return {"recovered", "clarify_required", "rejected"}


@pytest.mark.parametrize(
    "case",
    [case for case in _load_cases() if case["case_id"] in DATASET_CASE_IDS],
    ids=lambda case: case["case_id"],
)
def test_dataset_intent_analyze_contract(case: dict):
    resp = client.post(
        "/api/v1/intent/analyze",
        json={
            "conversation_id": f"dataset-{case['case_id']}",
            "user_id": "pytest",
            "channel": "web",
            "utterance": case["input"],
            "history": [],
            "memory": [],
            "resource_catalog": [],
            "ui_context": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    selected = data.get("selected_intent") or {}
    execution_intent = data.get("execution_intent") or {}

    assert selected.get("intent_code") == case["expected_intent"]
    assert execution_intent.get("mode") == case["expected_mode"]
    assert data.get("decision") in _expected_decision(case)
