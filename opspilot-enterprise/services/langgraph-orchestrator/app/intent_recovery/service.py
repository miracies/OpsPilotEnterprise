from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from opspilot_schema.intent import IntentCandidate, IntentRecoverInput, IntentRecoveryRun
from opspilot_schema.policy_rule import RiskEvaluationInput

from app.policy.engine import evaluate as evaluate_risk
from app.storage.db import execute

from .ontology import IntentSpec, list_intents
from .scorer import compute_final_score, decide_score
from .slot_extractor import build_evidence_refs, extract_slots, normalize_utterance


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_environment(slot_map: dict[str, Any]) -> str:
    env = slot_map.get("environment")
    return str(env or "prod")


def _keyword_score(spec: IntentSpec, utterance: str) -> float:
    text = normalize_utterance(utterance)
    if not spec.keywords:
        return 0.0
    hits = sum(1 for keyword in spec.keywords if keyword.lower() in text or keyword in utterance)
    score = min(1.0, hits / max(2, len(spec.keywords) / 2))
    if spec.action == "vm_power" and any(token in text for token in ("power on", "power off", "turn on", "turn off", "打开", "开启", "关闭", "关机", "开机")):
        score = max(score, 0.95)
    if spec.action == "vm_status" and any(token in text for token in ("power state", "状态", "运行状态", "电源状态", "status")):
        score = max(score, 0.9)
    if spec.action == "service_restart" and any(token in text for token in ("restart service", "service restart", "重启服务", "service")):
        score = max(score, 0.95)
    return score


def _entity_match(slot_map: dict[str, Any]) -> float:
    return 0.9 if slot_map.get("target_object") else 0.25


def _slot_completeness(spec: IntentSpec, slot_map: dict[str, Any]) -> tuple[float, list[str]]:
    missing = [name for name in spec.required_slots if slot_map.get(name) in (None, "")]
    if not spec.required_slots:
        return 1.0, []
    completeness = (len(spec.required_slots) - len(missing)) / len(spec.required_slots)
    return max(0.0, min(1.0, completeness)), missing


def _memory_boost(inp: IntentRecoverInput, spec: IntentSpec) -> float:
    text = " ".join(inp.memory or []) + " " + " ".join(str(item.get("content", "")) for item in inp.history or [])
    text = text.lower()
    if any(hint.lower() in text for hint in spec.memory_hints):
        return 0.8
    if spec.domain in text:
        return 0.55
    return 0.15


def _build_candidate(inp: IntentRecoverInput, spec: IntentSpec) -> IntentCandidate:
    slots = extract_slots(inp.utterance, inp.history)
    slot_map = {slot.name: slot.value for slot in slots}
    slot_completeness, missing = _slot_completeness(spec, slot_map)
    rules = _keyword_score(spec, inp.utterance)
    entity_match = _entity_match(slot_map)
    memory_boost = _memory_boost(inp, spec)
    llm_rerank = rules
    score_result = compute_final_score(
        rules=rules,
        slot_completeness=slot_completeness,
        entity_match=entity_match,
        memory_boost=memory_boost,
        llm_rerank=llm_rerank,
    )
    resource_scope = str(slot_map.get("resource_scope") or spec.resource_scope)
    environment = _pick_environment(slot_map)
    risk = evaluate_risk(
        RiskEvaluationInput(
            domain=spec.domain,
            action=spec.action,
            environment=environment if environment in {"dev", "test", "staging", "prod"} else "prod",
            resource_scope=resource_scope if resource_scope in {"single", "multiple", "cluster", "global"} else "single",
        )
    )
    return IntentCandidate(
        intent_code=spec.intent_code,
        domain=spec.domain,
        action=spec.action,
        description=spec.description,
        resource_scope=resource_scope,  # type: ignore[arg-type]
        environment=environment,
        memory_refs=list(inp.memory or []),
        score=score_result.final,
        score_breakdown=score_result.breakdown,
        slots=slots,
        missing_slots=missing,
        inferred_environment=environment,
        inferred_risk_level=risk.risk_level,
        evidence=build_evidence_refs(inp.utterance, slots),
    )


def persist_run(run: IntentRecoveryRun) -> None:
    execute(
        """
        INSERT OR REPLACE INTO op_intent_runs(
            run_id, conversation_id, user_id, channel, tenant_id, raw_utterance,
            normalized_text, decision, chosen_intent, clarify_reasons, rejected_reasons, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.run_id,
            run.conversation_id,
            run.user_id,
            run.channel,
            run.tenant_id,
            run.raw_utterance,
            run.normalized_utterance,
            run.decision,
            run.chosen_intent.intent_code if run.chosen_intent else None,
            json.dumps(run.clarify_reasons, ensure_ascii=False),
            json.dumps(run.rejected_reasons, ensure_ascii=False),
            run.created_at,
        ),
    )
    execute("DELETE FROM op_intent_candidates WHERE run_id=?", (run.run_id,))
    for index, candidate in enumerate(run.candidates, start=1):
        execute(
            """
            INSERT INTO op_intent_candidates(
                run_id, rank_no, intent_code, domain_name, action_name, score,
                score_breakdown, slots_json, missing_slots, evidence_json, inferred_risk, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                index,
                candidate.intent_code,
                candidate.domain,
                candidate.action,
                candidate.score,
                json.dumps(candidate.score_breakdown.model_dump(), ensure_ascii=False),
                json.dumps([slot.model_dump() for slot in candidate.slots], ensure_ascii=False),
                json.dumps(candidate.missing_slots, ensure_ascii=False),
                json.dumps([ev.model_dump() for ev in candidate.evidence], ensure_ascii=False),
                candidate.inferred_risk_level,
                run.created_at,
            ),
        )


def recover(inp: IntentRecoverInput) -> IntentRecoveryRun:
    run_id = f"ir_{uuid.uuid4().hex[:12]}"
    candidates = sorted((_build_candidate(inp, spec) for spec in list_intents()), key=lambda item: item.score, reverse=True)
    top1 = candidates[0].score if candidates else 0.0
    top2 = candidates[1].score if len(candidates) > 1 else 0.0
    chosen = candidates[0] if candidates else None
    any_missing = bool(chosen and chosen.missing_slots)
    decision = decide_score(top1=top1, top2=top2, any_missing_slot=any_missing)
    clarify_reasons: list[str] = []
    rejected_reasons: list[str] = []
    if decision == "clarify_required" and chosen:
        if chosen.missing_slots:
            clarify_reasons.append(f"缺少关键槽位: {', '.join(chosen.missing_slots)}")
        if top1 - top2 < 0.15:
            clarify_reasons.append("候选意图分差不足，需要确认")
    if decision == "rejected":
        rejected_reasons.append("未找到足够明确的意图候选")
    run = IntentRecoveryRun(
        run_id=run_id,
        conversation_id=inp.conversation_id,
        user_id=inp.user_id,
        channel=inp.channel,
        tenant_id=inp.tenant_id,
        raw_utterance=inp.utterance,
        normalized_utterance=normalize_utterance(inp.utterance),
        candidates=candidates,
        chosen_intent=chosen,
        decision=decision,  # type: ignore[arg-type]
        clarify_reasons=clarify_reasons,
        rejected_reasons=rejected_reasons,
        created_at=_now(),
    )
    persist_run(run)
    return run
