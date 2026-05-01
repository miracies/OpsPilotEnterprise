"""Optional live API evaluation wrapper for the intent-understanding script.

This test is intentionally skipped by default because it requires locally running
api-bff and langgraph-orchestrator services. Enable it with RUN_LIVE_INTENT_EVAL=1.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "eval_intent_understanding.py"


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("eval_intent_understanding", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(os.environ.get("RUN_LIVE_INTENT_EVAL") != "1", reason="requires live local services")
def test_live_intent_evaluation_thresholds():
    module = _load_eval_module()
    report = module.run_evaluation()
    summary = report["summary"]
    results = [item for item in report["results"] if item.get("status") != "skipped"]
    assert results, "live evaluation should execute at least one case"

    high_risk_failures = [item for item in results if item.get("status") == "high_risk_fail"]
    assert high_risk_failures == []

    passed = summary.get("passed", 0)
    partial = summary.get("partial", 0)
    min_pass_rate = float(os.environ.get("LIVE_INTENT_MIN_PASS_RATE", "0.7"))
    acceptable_rate = (passed + partial) / len(results)
    assert acceptable_rate >= min_pass_rate, {
        "summary": summary,
        "root_causes": report.get("root_causes", {}),
        "acceptable_rate": acceptable_rate,
        "min_pass_rate": min_pass_rate,
    }
