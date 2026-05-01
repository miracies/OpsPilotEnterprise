"""Focused tests for AlertKnowledge reasoning behavior."""
from __future__ import annotations

import asyncio
import os
import sys

ORCHESTRATOR_PATH = os.path.join(os.path.dirname(__file__), "..", "services", "langgraph-orchestrator")
sys.path.insert(0, ORCHESTRATOR_PATH)

from app.agents import RemediationAgent, RootCauseAgent

for _module_name in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
    del sys.modules[_module_name]
if ORCHESTRATOR_PATH in sys.path:
    sys.path.remove(ORCHESTRATOR_PATH)


def test_root_cause_agent_gates_on_missing_evidence():
    result = asyncio.run(
        RootCauseAgent().run(
            {
                "evidence": [{"evidence_id": "ev-1", "source_type": "event"}],
                "topology": {},
                "articles": [{"id": "AK-1", "title": "VM CPU"}],
                "missing_critical_evidence": ["metric", "detail"],
                "sufficiency_score": 0.25,
                "freshness_score": 1.0,
                "contradictions": [],
            }
        )
    )
    assert result["conclusion_status"] == "insufficient_evidence"
    assert result["winning_hypothesis"]["missing_evidence"] == ["metric", "detail"]


def test_remediation_agent_surfaces_knowledge_actions():
    result = asyncio.run(
        RemediationAgent().run(
            {
                "root_cause": {"summary": "资源压力或性能瓶颈导致异常"},
                "safe_actions": ["collect_vm_metrics"],
                "approval_actions": ["vmware.vm_migrate"],
            }
        )
    )
    assert "collect_vm_metrics" in result["recommended_actions"][0]
    assert "vmware.vm_migrate" in result["recommended_actions"][1]
    assert result["safe_actions"] == ["collect_vm_metrics"]
    assert result["approval_actions"] == ["vmware.vm_migrate"]
