from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "data" / "intent_understanding_cases.json"
OUT_DIR = ROOT / "tmp" / "intent-eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)
API_REPORT_PATH = OUT_DIR / "api-report.json"

BFF_BASE = os.environ.get("INTENT_EVAL_BFF_BASE", "http://127.0.0.1:8000").rstrip("/")
ORCH_BASE = os.environ.get("INTENT_EVAL_ORCH_BASE", "http://127.0.0.1:8010").rstrip("/")
TARGETED_CHAT_CASES = {"J001", "J002", "J003", "J005", "J006", "J007", "J008", "J015"}


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def call_intent_analyze(case: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "conversation_id": f"intent-eval-{case['case_id']}",
        "user_id": "web-user",
        "channel": "web",
        "utterance": case["input"],
        "history": [],
        "memory": [],
        "ui_context": {
            "connection_id": "conn-vcenter-prod",
            "environment": "prod",
        },
    }
    resp = requests.post(f"{ORCH_BASE}/api/v1/intent/analyze", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["data"]


def call_chat(case: dict[str, Any]) -> dict[str, Any]:
    session_id = f"intent-eval-chat-{case['case_id']}-{int(time.time() * 1000)}"
    send = requests.post(
        f"{BFF_BASE}/api/v1/chat/sessions/{session_id}/messages",
        json={"message": case["input"], "mode": "orchestrator_v2"},
        timeout=120,
    )
    send.raise_for_status()
    initial = send.json()["data"]
    msg_id = initial["id"]
    deadline = time.time() + 45
    latest = initial
    while time.time() < deadline:
        time.sleep(1.5)
        messages = requests.get(f"{BFF_BASE}/api/v1/chat/sessions/{session_id}/messages", timeout=120).json()["data"]
        target = next((item for item in messages if item["id"] == msg_id), None)
        if target:
            latest = target
            if target.get("status") in {"completed", "failed"}:
                break
    return {"session_id": session_id, "message": latest}


def call_chat_then_clarify(case: dict[str, Any]) -> dict[str, Any]:
    result = call_chat(case)
    message = result["message"]
    clarify_card = message.get("clarify_card") or {}
    selection = case.get("page_followup_selection") or (
        (clarify_card.get("candidate_targets") or [{}])[-1].get("label")
    )
    if not clarify_card.get("interaction_id") or not selection:
        result["clarify_followup"] = None
        return result
    follow = requests.post(
        f"{BFF_BASE}/api/v1/interactions/clarify/{clarify_card['interaction_id']}/answer",
        json={"selected_choice": selection, "free_text": None, "responded_by": "intent-eval"},
        timeout=180,
    )
    follow.raise_for_status()
    result["clarify_followup"] = follow.json()["data"]
    return result


def infer_root_causes(case: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    causes: list[str] = []
    expected_intent = case["expected_intent"]
    actual_intent = actual.get("intent")
    if expected_intent.startswith("resource.") and actual.get("decision") == "rejected":
        causes.append("resource_query_rejected")
    if expected_intent == "generic_ops_qa" and actual.get("decision") == "rejected":
        causes.append("knowledge_fallback_wrong")
    if actual_intent and expected_intent not in {actual_intent, "generic_ops_qa"}:
        if not expected_intent.startswith("resource."):
            causes.append("intent_misroute")
    if case["expected_next_step"] == "clarify" and not actual.get("has_clarify"):
        causes.append("clarify_missing")
    target = case.get("expected_target_resolution")
    if target and actual.get("target_resolution") in {None, ""} and case["category"] in {
        "host_vm_diagnosis",
        "resource_query",
    }:
        causes.append("slot_missing_false_positive")
    return list(dict.fromkeys(causes))


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    if case["current_phase"] != "read_only":
        return {
            "case_id": case["case_id"],
            "input": case["input"],
            "status": "skipped",
            "reason": "deferred_real_exec",
            "validation_layer": case["validation_layer"],
        }

    strategy = case["evaluation_strategy"]
    if case["validation_layer"] == "api" and case["case_id"] not in TARGETED_CHAT_CASES and strategy != "chat_then_clarify":
        strategy = "analyze"

    try:
        raw: dict[str, Any]
        if strategy == "analyze":
            analyze = call_intent_analyze(case)
            selected = analyze.get("selected_intent") or {}
            actual = {
                "decision": analyze.get("decision"),
                "intent": selected.get("intent_code"),
                "mode": (analyze.get("execution_intent") or {}).get("mode"),
                "target_resolution": selected.get("target_object_resolved") or selected.get("target_object_raw"),
                "has_clarify": bool(analyze.get("clarify_card")),
                "kind": None,
                "content": "",
                "tool_traces": [],
                "evidence_refs": analyze.get("evidence_refs") or [],
            }
            raw = {"analyze": analyze}
        elif strategy == "chat_then_clarify":
            chain = call_chat_then_clarify(case)
            message = chain["message"]
            followup = chain.get("clarify_followup") or {}
            intent_recovery = message.get("intent_recovery") or {}
            chosen = intent_recovery.get("chosen_intent") or {}
            actual = {
                "decision": intent_recovery.get("decision"),
                "intent": chosen.get("intent_code"),
                "mode": (message.get("execution_intent") or {}).get("mode"),
                "target_resolution": chosen.get("target_object_resolved") or chosen.get("target_object_raw"),
                "has_clarify": bool(message.get("clarify_card")),
                "kind": message.get("kind"),
                "content": message.get("content") or "",
                "tool_traces": message.get("tool_traces") or [],
                "evidence_refs": message.get("evidence_refs") or [],
                "clarify_followup_next_action": followup.get("next_action"),
                "clarify_followup_message": followup.get("next_message"),
                "clarify_followup_diagnosis_id": followup.get("diagnosis_id"),
            }
            raw = chain
        else:
            chat = call_chat(case)
            message = chat["message"]
            intent_recovery = message.get("intent_recovery") or {}
            chosen = intent_recovery.get("chosen_intent") or {}
            actual = {
                "decision": intent_recovery.get("decision"),
                "intent": chosen.get("intent_code"),
                "mode": (message.get("execution_intent") or {}).get("mode"),
                "target_resolution": chosen.get("target_object_resolved") or chosen.get("target_object_raw"),
                "has_clarify": bool(message.get("clarify_card")),
                "kind": message.get("kind"),
                "content": message.get("content") or "",
                "tool_traces": message.get("tool_traces") or [],
                "evidence_refs": message.get("evidence_refs") or [],
            }
            raw = chat
    except Exception as exc:  # noqa: BLE001
        return {
            "case_id": case["case_id"],
            "persona": case["persona"],
            "category": case["category"],
            "input": case["input"],
            "status": "failed",
            "checks": {},
            "actual": {},
            "root_causes": ["evaluation_runtime_error"],
            "raw": {"error": str(exc)},
        }

    checks: dict[str, bool] = {
        "intent": actual.get("intent") == case["expected_intent"],
        "mode": actual.get("mode") == case["expected_mode"],
    }

    if strategy == "analyze":
        if case["expected_next_step"] == "clarify":
            checks["next_step"] = actual.get("decision") == "clarify_required" or actual.get("has_clarify")
        elif case["expected_next_step"] == "approval":
            checks["next_step"] = actual.get("mode") in {"plan", "execute"}
        else:
            checks["next_step"] = actual.get("decision") in {"recovered", "clarify_required"}
    else:
        checks["next_step"] = (
            case["expected_next_step"] == "clarify"
            and actual.get("has_clarify")
        ) or (
            case["expected_next_step"] == "diagnose"
            and (
                "结论：" in actual.get("content", "")
                or bool(actual.get("clarify_followup_diagnosis_id"))
            )
        ) or (
            case["expected_next_step"] == "direct_answer"
            and not actual.get("has_clarify")
        ) or (
            case["expected_next_step"] == "approval"
            and actual.get("mode") in {"plan", "execute"}
        )

    if strategy == "analyze":
        checks["answer_shape"] = True
    elif case["expected_answer_shape"] and actual.get("content"):
        content = actual["content"]
        checks["answer_shape"] = any(token in content for token in case["expected_answer_shape"])
    elif actual.get("clarify_followup_message"):
        checks["answer_shape"] = any(
            token in actual["clarify_followup_message"] for token in case["expected_answer_shape"]
        )
    else:
        checks["answer_shape"] = False

    if case["category"] == "vmware_kb_search":
        checks["evidence"] = bool(actual.get("evidence_refs"))
    else:
        checks["evidence"] = True

    root_causes = infer_root_causes(case, actual)
    score = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    if score == total:
        status = "passed"
    elif score >= max(2, total - 1):
        status = "partial"
    else:
        status = "failed"
    if "execute_side_effect" in case["must_not_happen"] and "已自动推进执行" in actual.get("content", ""):
        status = "high_risk_fail"
        root_causes = list(dict.fromkeys(root_causes + ["unsafe_execution"]))

    return {
        "case_id": case["case_id"],
        "persona": case["persona"],
        "category": case["category"],
        "input": case["input"],
        "status": status,
        "checks": checks,
        "actual": actual,
        "root_causes": root_causes,
        "raw": raw,
    }


def run_evaluation(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases or load_cases()
    results = [evaluate_case(case) for case in cases]
    summary = Counter(result["status"] for result in results)
    by_root_cause = Counter(cause for result in results for cause in result.get("root_causes", []))
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": dict(summary),
        "root_causes": dict(by_root_cause),
        "results": results,
    }


def main() -> None:
    report = run_evaluation()
    API_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "root_causes": report["root_causes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
