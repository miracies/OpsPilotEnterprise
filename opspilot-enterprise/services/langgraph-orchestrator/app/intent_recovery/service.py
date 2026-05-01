from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from opspilot_schema.intent import IntentCandidate, IntentRecoverInput, IntentRecoveryRun
from opspilot_schema.policy_rule import RiskEvaluationInput

from app.policy.engine import evaluate as evaluate_risk
from app.storage.db import execute
from app.storage.postgres import write_shadow_event

from .ontology import IntentSpec, list_intents
from .scorer import compute_final_score, decide_score
from .slot_extractor import build_evidence_refs, extract_slots, normalize_utterance, resolve_target_candidates

_RESOURCE_SUMMARY_PATTERNS = [
    re.compile(r"(vcenter|vsphere)?.*(生产|prod).*(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储|集群|cluster).*(多少|数量|几个|几台|总数|count)", re.I),
    re.compile(r"(vcenter|vsphere)?.*(生产|prod).*(多少|数量|几个|几台|总数|count).*(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储|集群|cluster)", re.I),
    re.compile(r"(生产|prod).*(主机数量|host count|hosts?|datastore|数据存储|集群|cluster)", re.I),
    re.compile(r"(关机|开机|异常|非健康|容量不足|小于|低于).*(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储)", re.I),
    re.compile(r"(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储|集群|cluster).*(哪些|列表|列出|清单|有哪些|list)", re.I),
    re.compile(r"(cpu|内存|memory|使用率|性能|指标|iops|延迟|latency|吞吐|容量|剩余|关联|最高|最低).*(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储)", re.I),
    re.compile(r"(虚拟机|vm|主机|esxi|host|datastore|数据存储|存储).*(cpu|内存|memory|使用率|性能|指标|iops|延迟|latency|吞吐|容量|剩余|关联|最高|最低)", re.I),
    re.compile(r"conn-vcenter-prod.*(vm|虚拟机|主机|esxi|datastore|数据存储|集群|异常摘要)", re.I),
]
_RESOURCE_EXPORT_PATTERNS = [
    re.compile(r"(导出|export).*(vcenter|vsphere).*(生产|prod).*(虚拟机|vm).*(列表|list)?", re.I),
    re.compile(r"(vcenter|vsphere).*(生产|prod).*(虚拟机|vm).*(列表|list).*(导出|export)", re.I),
]
_GENERIC_OPS_QA_SHAPE_PATTERNS = [
    re.compile(r"是否会|会不会|影响|中断|丢包|风险|原理|注意事项|最佳实践", re.I),
    re.compile(r"可能是什么问题|怎么排查|会有问题吗|会影响业务吗", re.I),
    re.compile(r"\?|？"),
]
_GENERIC_OPS_QA_CONTEXT_PATTERNS = [
    re.compile(r"热迁移|vmotion|迁移", re.I),
    re.compile(r"k8s|kubernetes|deployment", re.I),
    re.compile(r"esxi|主机|host|vcenter|vsphere|vmware", re.I),
]
_SCALE_ACTION_PATTERNS = [
    re.compile(r"\bscale\b", re.I),
    re.compile(r"扩到|扩容|缩到|副本", re.I),
]
_RESTART_ACTION_PATTERNS = [
    re.compile(r"\brestart\b", re.I),
    re.compile(r"重启", re.I),
]
_VMWARE_WRITE_ACTION_PATTERNS = [
    re.compile(r"开机|关机|上电|断电|power\s*on|power\s*off", re.I),
    re.compile(r"迁移|热迁移|vmotion|migrate", re.I),
    re.compile(r"重启|restart|reboot", re.I),
    re.compile(r"删除|delete|destroy", re.I),
    re.compile(r"创建.*快照|打.*快照|snapshot", re.I),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_ip_like(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value.strip()))


def _pick_environment(slot_map: dict[str, Any]) -> str:
    env = slot_map.get("environment")
    return str(env or "prod")


def _keyword_score(spec: IntentSpec, utterance: str) -> float:
    text = normalize_utterance(utterance)
    has_question_shape = any(p.search(utterance) for p in _GENERIC_OPS_QA_SHAPE_PATTERNS)
    has_explicit_host_target = bool(
        re.search(r"(?:\d{1,3}\.){3}\d{1,3}", utterance)
        or re.search(r"\besx\d+[a-z0-9._-]*\b", utterance, re.I)
        or re.search(r"\b[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+\b", utterance)
    )
    if not spec.keywords:
        return 0.0
    hits = sum(1 for keyword in spec.keywords if keyword.lower() in text or keyword in utterance)
    score = min(1.0, hits / max(2, len(spec.keywords) / 2))
    if spec.action == "vm_power" and any(token in text for token in ("power on", "power off", "turn on", "turn off", "打开", "开启", "关闭", "关机", "开机")):
        score = max(score, 0.95)
    if spec.action == "vm_status" and any(token in text for token in ("power state", "状态", "运行状态", "电源状态", "status")):
        score = max(score, 0.9)
    if spec.action == "vm_status" and any(token in text for token in ("主机", "host", "esxi")) and not any(
        token in text for token in ("虚拟机", " vm ", "vm")
    ):
        score = min(score, 0.2)
    if spec.action == "service_restart" and any(token in text for token in ("restart service", "service restart", "重启服务", "service")):
        score = max(score, 0.95)
    if spec.action == "vmware_kb_search":
        vmware_ctx = any(token in text for token in ("vmware", "esxi", "vcenter", "vsphere"))
        doc_intent = any(
            token in text
            for token in ("download", "install", "version", "patch", "kb", "article", "compatibility", "文档", "下载", "版本", "补丁", "兼容")
        )
        if vmware_ctx and doc_intent:
            score = max(score, 0.96)
    if spec.action == "vcenter_inventory_summary" and any(p.search(utterance) for p in _RESOURCE_SUMMARY_PATTERNS):
        score = max(score, 0.98)
    if spec.action == "vcenter_vm_export":
        if any(p.search(utterance) for p in _RESOURCE_EXPORT_PATTERNS):
            score = max(score, 0.98)
        else:
            score = min(score, 0.25)
    if spec.action == "write_blocked":
        if (
            any(p.search(utterance) for p in _VMWARE_WRITE_ACTION_PATTERNS)
            and any(token in text for token in ("vmware", "vcenter", "vsphere", "esxi", "虚拟机", "主机", "datastore", "集群"))
            and not has_question_shape
        ):
            score = max(score, 0.97)
        else:
            score = min(score, 0.25)
    if spec.action == "generic_ops_qa":
        has_ops_context = any(p.search(utterance) for p in _GENERIC_OPS_QA_CONTEXT_PATTERNS)
        has_qa_shape = has_question_shape
        if has_ops_context and has_qa_shape:
            score = max(score, 0.95)
        if (
            any(token in text for token in ("overallstatus", "yellow", "red"))
            and any(token in utterance for token in ("可能", "问题", "排查"))
        ):
            score = max(score, 0.98)
        if any(p.search(utterance) for p in _SCALE_ACTION_PATTERNS + _RESTART_ACTION_PATTERNS) and not has_question_shape:
            score = min(score, 0.2)
    if spec.action == "scale_deployment":
        if "deployment" in text and (any(p.search(utterance) for p in _SCALE_ACTION_PATTERNS) or re.search(r"\bto\s+\d+\b", text)):
            score = max(score, 0.96)
    if spec.action == "service_restart":
        if any(p.search(utterance) for p in _RESTART_ACTION_PATTERNS):
            score = max(score, 0.92)
    if spec.action == "host_diagnose":
        has_host_diag = any(token in text for token in ("主机", "host", "esxi")) and any(
            token in text for token in ("健康", "状态", "health", "status", "overallstatus", "yellow", "red", "分析")
        )
        has_ip = bool(re.search(r"(?:\d{1,3}\.){3}\d{1,3}", utterance))
        if has_host_diag or has_ip:
            score = max(score, 0.94)
        if (has_question_shape or ("可能" in utterance and "问题" in utterance)) and not has_explicit_host_target:
            score = min(score, 0.35)
    if spec.intent_code == "knowledge.explain" and any(token in text for token in ("主机", "host", "esxi")) and any(
        token in text for token in ("健康", "health", "分析", "诊断", "状态", "overallstatus", "yellow", "red")
    ):
        score = min(score, 0.2)
    return score


def _entity_match(slot_map: dict[str, Any]) -> float:
    if slot_map.get("target_object_resolved"):
        return 1.0
    if slot_map.get("target_object"):
        return 0.9
    return 0.25


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


def _domain_gate_score(spec: IntentSpec, utterance: str) -> float:
    text = normalize_utterance(utterance)
    has_host_cue = any(token in text for token in ("主机", "host", "esxi"))
    has_host_diag = has_host_cue and any(
        token in text for token in ("健康", "health", "分析", "diagnose", "状态", "overallstatus", "yellow", "red")
    )
    has_host_ip = bool(re.search(r"(?:\d{1,3}\.){3}\d{1,3}", utterance)) and has_host_cue
    has_vm_cue = any(token in text for token in ("虚拟机", " vm ", "vm", "test-vm"))
    has_vm_status = has_vm_cue and any(token in text for token in ("电源状态", "运行状态", "status", "power state"))
    has_doc = any(token in text for token in ("download", "install", "version", "patch", "kb", "article", "文档", "下载"))
    has_resource_summary = any(pattern.search(utterance) for pattern in _RESOURCE_SUMMARY_PATTERNS)
    has_resource_export = any(pattern.search(utterance) for pattern in _RESOURCE_EXPORT_PATTERNS)
    has_vmware_write = any(pattern.search(utterance) for pattern in _VMWARE_WRITE_ACTION_PATTERNS) and any(
        token in text for token in ("vmware", "vcenter", "vsphere", "esxi", "虚拟机", "主机", "datastore", "集群")
    )
    has_generic_qa = any(pattern.search(utterance) for pattern in _GENERIC_OPS_QA_SHAPE_PATTERNS) and any(
        pattern.search(utterance) for pattern in _GENERIC_OPS_QA_CONTEXT_PATTERNS
    )
    has_question_shape = any(pattern.search(utterance) for pattern in _GENERIC_OPS_QA_SHAPE_PATTERNS)
    has_scale_action = any(pattern.search(utterance) for pattern in _SCALE_ACTION_PATTERNS)
    has_restart_action = any(pattern.search(utterance) for pattern in _RESTART_ACTION_PATTERNS)

    if spec.intent_code == "vmware.host.diagnose":
        if re.search(r"可能.*问题|怎么排查|what.*wrong", utterance, re.I):
            return 0.0
        if has_generic_qa or has_resource_summary or has_resource_export:
            return 0.0
        return 1.0 if (has_host_diag or has_host_ip) else 0.0
    if spec.intent_code == "vmware.vm.status":
        return 0.9 if has_vm_status else 0.0
    if spec.intent_code == "resource.vcenter.inventory_summary":
        return 1.0 if has_resource_summary else 0.0
    if spec.intent_code == "resource.vcenter.vm_export":
        return 1.0 if has_resource_export else 0.0
    if spec.intent_code == "vmware.write.blocked":
        return 1.0 if has_vmware_write and not has_question_shape and not has_resource_summary and not has_resource_export else 0.0
    if spec.intent_code == "generic_ops_qa":
        if (has_scale_action or has_restart_action) and not has_question_shape:
            return 0.0
        return 1.0 if has_generic_qa and not has_doc else 0.0
    if spec.intent_code == "knowledge.vmware_kb_search":
        return 1.0 if has_doc and any(token in text for token in ("vmware", "esxi", "vcenter", "vsphere")) else 0.0
    if spec.intent_code == "k8s.scale":
        if has_question_shape:
            return 0.0
        return 1.0 if ("deployment" in text and has_scale_action) else 0.0
    if spec.intent_code == "host.service.restart":
        if "deployment" in text or "k8s" in text or "kubernetes" in text or has_question_shape:
            return 0.0
        return 1.0 if has_restart_action else 0.0
    if spec.domain == "knowledge" and has_host_diag:
        return 0.0
    return 0.0


def _target_resolution_score(spec: IntentSpec, slot_map: dict[str, Any]) -> float:
    if spec.required_slots and "target_object" in spec.required_slots:
        if slot_map.get("target_object_resolved"):
            return 1.0
        if slot_map.get("target_object"):
            return 0.65
        return 0.0
    return 0.0


def _post_adjust_candidate(candidate: IntentCandidate) -> IntentCandidate:
    if candidate.intent_code == "vmware.host.diagnose" and candidate.target_object_raw and not candidate.target_object_resolved:
        candidate.score = round(max(0.0, candidate.score - 0.12), 4)
    if candidate.intent_code in {"resource.vcenter.inventory_summary", "resource.vcenter.vm_export"}:
        if candidate.environment in {"prod", "test", "dev", "staging"}:
            candidate.score = round(min(1.0, candidate.score + 0.05), 4)
        if candidate.score_breakdown.rules < 0.2:
            candidate.score = round(max(0.0, candidate.score - 0.18), 4)
    if candidate.intent_code == "generic_ops_qa" and candidate.score_breakdown.rules < 0.5:
        candidate.score = round(max(0.0, candidate.score - 0.12), 4)
    return candidate


def _build_candidate(inp: IntentRecoverInput, spec: IntentSpec) -> IntentCandidate:
    slots = extract_slots(
        inp.utterance,
        inp.history,
        intent_hint=f"{spec.domain}.{spec.action}",
        resource_catalog=inp.resource_catalog,
    )
    slot_map = {slot.name: slot.value for slot in slots}
    if spec.intent_code in {"resource.vcenter.inventory_summary", "resource.vcenter.vm_export"} and not slot_map.get("environment"):
        slot_map["environment"] = _pick_environment(slot_map)
    slot_completeness, missing = _slot_completeness(spec, slot_map)
    rules = _keyword_score(spec, inp.utterance)
    entity_match = _entity_match(slot_map)
    if spec.action == "vmware_kb_search" and slot_map.get("query_text"):
        entity_match = max(entity_match, 0.9)
    memory_boost = _memory_boost(inp, spec)
    llm_rerank = rules
    domain_gate_score = _domain_gate_score(spec, inp.utterance)
    target_resolution_score = _target_resolution_score(spec, slot_map)
    score_result = compute_final_score(
        rules=rules,
        slot_completeness=slot_completeness,
        entity_match=entity_match,
        memory_boost=memory_boost,
        llm_rerank=llm_rerank,
        domain_gate_score=domain_gate_score,
        target_resolution_score=target_resolution_score,
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
    resolution_refs = resolve_target_candidates(
        str(slot_map.get("target_object_raw") or slot_map.get("target_object") or "") or None,
        inp.resource_catalog,
        expected_type=str(slot_map.get("target_type") or "") or None,
    )
    candidate = IntentCandidate(
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
        target_object_raw=str(slot_map.get("target_object_raw") or slot_map.get("target_object") or "") or None,
        target_object_resolved=str(slot_map.get("target_object_resolved") or "") or None,
        target_type=str(slot_map.get("target_type") or "") or None,
        resolution_confidence=float(slot_map.get("target_resolution_confidence") or 0.0),
        resolution_refs=resolution_refs,
    )
    return _post_adjust_candidate(candidate)


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
    write_shadow_event("op_intent_runs", run.run_id, run.model_dump())


def recover(inp: IntentRecoverInput) -> IntentRecoveryRun:
    run_id = f"ir_{uuid.uuid4().hex[:12]}"
    candidates = sorted((_build_candidate(inp, spec) for spec in list_intents()), key=lambda item: item.score, reverse=True)
    top1 = candidates[0].score if candidates else 0.0
    top2 = candidates[1].score if len(candidates) > 1 else 0.0
    chosen = candidates[0] if candidates else None
    any_missing = bool(chosen and chosen.missing_slots)
    decision = decide_score(top1=top1, top2=top2, any_missing_slot=any_missing)
    host_target_direct = bool(
        chosen
        and chosen.intent_code == "vmware.host.diagnose"
        and chosen.target_object_raw
        and (
            chosen.target_object_resolved
            or "." in str(chosen.target_object_raw)
            or _is_ip_like(chosen.target_object_raw)
        )
    )
    if chosen and host_target_direct:
        decision = "recovered" if not chosen.missing_slots else "clarify_required"
    elif chosen and chosen.intent_code == "vmware.host.diagnose" and chosen.target_object_raw:
        decision = "clarify_required"
    if chosen and chosen.intent_code in {"generic_ops_qa", "resource.vcenter.inventory_summary", "resource.vcenter.vm_export", "vmware.write.blocked"}:
        if not chosen.missing_slots:
            decision = "recovered"
    if chosen and len(chosen.resolution_refs) > 1 and (
        chosen.resolution_confidence < 0.9
        or ("." not in str(chosen.target_object_raw or ""))
    ):
        decision = "clarify_required"
    clarify_reasons: list[str] = []
    rejected_reasons: list[str] = []
    if decision == "clarify_required" and chosen:
        if chosen.missing_slots:
            clarify_reasons.append(f"缺少关键槽位: {', '.join(chosen.missing_slots)}")
        if chosen.target_object_raw and not chosen.target_object_resolved:
            clarify_reasons.append(f"未在当前连接中解析到目标对象: {chosen.target_object_raw}")
        if len(chosen.resolution_refs) > 1 and chosen.resolution_confidence < 0.9:
            clarify_reasons.append("目标对象存在多个候选，需要确认")
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


