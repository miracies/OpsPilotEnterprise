from __future__ import annotations

import re
from typing import Any

from opspilot_schema.intent import (
    ExecutionIntent,
    IntentAnalyzeInput,
    IntentAnalyzeResponse,
    IntentRecoverInput,
    RiskContext,
)

from .service import recover
from .slot_extractor import normalize_utterance

_WRITE_ACTION_HINTS = {
    "vm_power",
    "write_blocked",
    "service_restart",
    "scale_deployment",
    "restart_vm",
    "vm_guest_restart",
    "host_restart",
    "run_job",
}

_CONSULT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"先看|先看看|看一下|看看",
        r"怎么做|如何做|如何处理|处理建议|建议",
        r"分析一下|分析下|评估一下|评估下",
        r"what is|how to|how do i|explain|why",
        r"是否|会不会|风险|影响",
    )
]

_NORMALIZATION_MAP = {
    "重启一下": "restart",
    "重启下": "restart",
    "开机": "power on",
    "上电": "power on",
    "关机": "power off",
    "断电": "power off",
    "虚机": "虚拟机",
    "esx ": "esxi ",
}


def _context_completion(inp: IntentAnalyzeInput) -> tuple[str, dict[str, Any], list[str]]:
    utterance = (inp.utterance or "").strip()
    hints: dict[str, Any] = {}
    memory_refs: list[str] = []

    environment = ""
    if isinstance(inp.ui_context, dict):
        environment = str(inp.ui_context.get("environment") or "").strip()
        default_conn = str(inp.ui_context.get("connection_id") or "").strip()
        if default_conn:
            hints["connection_id"] = default_conn
            memory_refs.append(f"ui:{default_conn}")

    if not environment:
        for item in inp.memory:
            lowered = item.lower()
            if "prod" in lowered or "生产" in item:
                environment = "prod"
                memory_refs.append("memory:environment=prod")
                break
            if "test" in lowered or "测试" in item:
                environment = "test"
                memory_refs.append("memory:environment=test")
                break

    if environment and not re.search(r"\b(prod|test|dev|staging)\b|生产|测试|开发|预发", utterance, re.I):
        utterance = f"{utterance} {environment}"
        hints["completed_environment"] = environment

    if inp.resource_catalog:
        hints["resource_catalog_count"] = len(inp.resource_catalog)
    hints["history_size"] = len(inp.history or [])
    return utterance, hints, memory_refs


def _semantic_normalization(utterance: str) -> str:
    text = utterance or ""
    for src, dst in _NORMALIZATION_MAP.items():
        text = text.replace(src, dst)
    return normalize_utterance(text)


def _execution_intent(
    normalized_utterance: str,
    *,
    action: str | None,
    prefer_execute: bool | None,
) -> ExecutionIntent:
    if prefer_execute is False:
        return ExecutionIntent(
            mode="read",
            reason="用户未明确要求副作用执行，当前只允许只读分析或查询。",
            guardrails=["non_execute_by_preference"],
        )

    if any(pattern.search(normalized_utterance) for pattern in _CONSULT_PATTERNS):
        mode = "plan" if (action or "") in _WRITE_ACTION_HINTS else "read"
        return ExecutionIntent(
            mode=mode,
            reason="识别到咨询或分析语义，允许只读分析/规划，不允许直接执行副作用动作。",
            guardrails=["consult_to_execute_blocked"],
        )

    mode = "execute"
    reason = "语义明确指向执行操作，允许进入执行或审批链路。"
    if action and action not in _WRITE_ACTION_HINTS:
        mode = "read"
        reason = "识别为只读查询或诊断意图，允许执行只读工具链，不允许副作用动作。"
    return ExecutionIntent(mode=mode, reason=reason, guardrails=[])


def _risk_context(chosen: dict[str, Any], normalized_utterance: str) -> RiskContext:
    env = str(chosen.get("environment") or chosen.get("inferred_environment") or "prod")
    scope = str(chosen.get("resource_scope") or "single")
    object_count = 1
    if " and " in normalized_utterance or "、" in normalized_utterance or "," in normalized_utterance:
        object_count = 2
    if scope in {"multiple", "cluster", "global"}:
        object_count = max(object_count, 2)
    return RiskContext(
        environment=env,
        resource_scope=scope if scope in {"single", "multiple", "cluster", "global"} else "single",
        object_count=object_count,
    )


def analyze_intent(body: IntentAnalyzeInput) -> IntentAnalyzeResponse:
    completed_utterance, context_hints, ctx_memory_refs = _context_completion(body)
    normalized_utterance = _semantic_normalization(completed_utterance)

    recovered = recover(
        IntentRecoverInput(
            conversation_id=body.conversation_id,
            user_id=body.user_id,
            channel=body.channel,
            utterance=normalized_utterance,
            tenant_id=body.tenant_id,
            history=body.history,
            memory=list(body.memory) + ctx_memory_refs,
            resource_catalog=body.resource_catalog,
        )
    )
    chosen = recovered.chosen_intent.model_dump() if recovered.chosen_intent else {}
    execution_intent = _execution_intent(
        normalized_utterance,
        action=chosen.get("action"),
        prefer_execute=body.prefer_execute,
    )
    risk_context = _risk_context(chosen, normalized_utterance)

    memory_refs = list(
        dict.fromkeys((recovered.chosen_intent.memory_refs if recovered.chosen_intent else []) + ctx_memory_refs)
    )
    evidence_refs = [item.ref_id for item in (recovered.chosen_intent.evidence if recovered.chosen_intent else [])]

    return IntentAnalyzeResponse(
        run_id=recovered.run_id,
        decision=recovered.decision,
        selected_intent=recovered.chosen_intent,
        candidates=recovered.candidates,
        execution_intent=execution_intent,
        risk_context=risk_context,
        context_hints=context_hints,
        normalized_utterance=normalized_utterance,
        memory_refs=memory_refs,
        evidence_refs=evidence_refs,
        clarify_reasons=recovered.clarify_reasons,
        rejected_reasons=recovered.rejected_reasons,
        rag_plan={"enabled": True, "queries": [normalized_utterance]} if normalized_utterance else {"enabled": False, "queries": []},
        run=recovered,
    )
