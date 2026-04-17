from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.intent import IntentRecoverInput
from opspilot_schema.interaction import ApprovalCreateRequest, ClarifyCreateRequest, ResourceRef, ResourceScope
from opspilot_schema.policy_rule import RiskEvaluationInput
from opspilot_schema.resume import PlanStep

from app.audit.checkpoint import upsert_checkpoint
from app.audit.events import append_audit_event, list_audit_events
from app.intent_recovery.service import recover
from app.interactions.approve import create_approval
from app.interactions.clarify import create_clarify
from app.policy.engine import evaluate as evaluate_risk

router = APIRouter(tags=["orchestrator-v2"])


class ChatV2Request(BaseModel):
    session_id: str
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    user_id: str = "web-user"
    channel: str = "web"


class ChatV2Response(BaseModel):
    session_id: str
    message_id: str
    assistant_message: str
    agent_name: str = "OrchestratorV2"
    kind: str = "text"
    reasoning_summary: dict[str, str]
    intent_recovery: dict[str, Any] | None = None
    clarify_card: dict[str, Any] | None = None
    approval_card: dict[str, Any] | None = None
    resume_card: dict[str, Any] | None = None
    audit_timeline: dict[str, Any] | None = None
    tool_traces: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_id() -> str:
    return f"msg-v2-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"


def _reasoning(intent: str, plan: str, result: str) -> dict[str, str]:
    return {
        "intent_understanding": intent,
        "execution_plan": plan,
        "result_summary": result,
    }


def _target_name(run: dict[str, Any]) -> str:
    chosen = run.get("chosen_intent") or {}
    for slot in chosen.get("slots", []):
        if slot.get("name") == "target_object":
            return str(slot.get("value"))
    return "未指定目标"


def _resource_scope_from_run(run: dict[str, Any]) -> ResourceScope:
    chosen = run.get("chosen_intent") or {}
    environment = chosen.get("environment") or chosen.get("inferred_environment") or "prod"
    target_name = _target_name(run)
    if target_name == "未指定目标":
        return ResourceScope(environment=environment, resources=[])
    return ResourceScope(environment=environment, resources=[ResourceRef(type=chosen.get("domain") or "resource", id=target_name, name=target_name)])


def _plan_steps_for_run(run: dict[str, Any]) -> list[PlanStep]:
    chosen = run.get("chosen_intent") or {}
    action = chosen.get("action") or "unknown"
    target_name = _target_name(run)
    environment = chosen.get("environment") or chosen.get("inferred_environment") or "prod"
    return [
        PlanStep(seq=1, type="read", action="validate_context", args={"target": target_name, "environment": environment}),
        PlanStep(seq=2, type="write", action=str(action), args={"target": target_name, "environment": environment}),
    ]


def _clarify_question(run: dict[str, Any]) -> tuple[str, list[str]]:
    chosen = run.get("chosen_intent") or {}
    missing_slots = chosen.get("missing_slots") or []
    if missing_slots:
        first = missing_slots[0]
        label_map = {
            "target_object": "请补充目标对象名称或 IP。",
            "environment": "请确认环境（prod/test/dev）。",
            "replicas": "请补充目标副本数。",
            "service_name": "请补充服务名。",
        }
        return label_map.get(first, f"请补充槽位：{first}"), []
    candidates = run.get("candidates") or []
    options = [f"{item['intent_code']} ({item['score']:.2f})" for item in candidates[:3]]
    return "系统识别到多个可能意图，请确认本次要执行哪一类操作。", options


def _audit_timeline(run_id: str) -> dict[str, Any]:
    events = list_audit_events(run_id)
    return {
        "run_id": run_id,
        "operator": "orchestrator",
        "decision_chain": [event.summary for event in events if event.event_type in {"RECOVER", "CLARIFY_CREATED", "APPROVE_CREATED", "APPROVE_DECIDED", "RESUME"}],
        "tool_outputs": [event.summary for event in events if event.event_type in {"PRE_EXEC", "POST_EXEC", "ROLLBACK"}],
        "events": [event.model_dump() for event in events],
    }


@router.post("/api/v1/orchestrate/chat-v2")
async def orchestrate_chat_v2(body: ChatV2Request):
    try:
        recovered = recover(
            IntentRecoverInput(
                conversation_id=body.session_id,
                user_id=body.user_id,
                channel=body.channel,
                utterance=body.message,
                history=body.history,
                memory=[str(item.get("content") or "") for item in body.history[-8:]],
            )
        )
        run = recovered.model_dump()
        append_audit_event(run_id=recovered.run_id, event_type="RECOVER", summary=f"恢复意图: {recovered.decision}")
        if recovered.decision == "rejected":
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="未能稳定恢复你的意图，请换一种说法或补充更明确的目标对象。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning("系统尝试恢复用户意图。", "基于规则、槽位和记忆做候选评分。", "意图恢复失败，未进入执行阶段。"),
                    intent_recovery=run,
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if recovered.decision == "clarify_required":
            question, choices = _clarify_question(run)
            clarify = create_clarify(
                ClarifyCreateRequest(
                    run_id=recovered.run_id,
                    question=question,
                    choices=choices,
                    allow_free_text=True,
                    reason_code="missing_slot" if recovered.missing_slots else "ambiguous_intent",
                )
            )
            append_audit_event(run_id=recovered.run_id, event_type="CLARIFY_CREATED", summary=question)
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=question,
                    kind="clarify",
                    reasoning_summary=_reasoning("系统已恢复到候选意图，但关键信息仍不足。", "发起 Clarify 交互补齐关键槽位或确认候选。", "当前未执行任何副作用操作，等待用户补充。"),
                    intent_recovery=run,
                    clarify_card=clarify.model_dump(),
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        chosen = recovered.chosen_intent
        assert chosen is not None
        risk = evaluate_risk(
            RiskEvaluationInput(
                domain=chosen.domain,
                action=chosen.action,
                environment=(chosen.environment or chosen.inferred_environment or "prod"),
                resource_scope=chosen.resource_scope,
            )
        )
        plan_steps = _plan_steps_for_run(run)
        resource_scope = _resource_scope_from_run(run)
        if risk.deny:
            append_audit_event(run_id=recovered.run_id, event_type="FAILED", summary="命中拒绝策略，终止执行")
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="该操作命中高风险拒绝策略，当前不能直接执行。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning("系统已恢复出可执行意图。", "通过风险策略引擎评估环境、范围和动作类型。", "命中 L4/deny 策略，流程已中止。"),
                    intent_recovery=run,
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if risk.require_approval:
            approval = create_approval(
                ApprovalCreateRequest(
                    run_id=recovered.run_id,
                    summary=f"对 {resource_scope.resources[0].name if resource_scope.resources else '目标对象'} 执行 {chosen.action}",
                    domain=chosen.domain,
                    action=chosen.action,
                    risk_level=risk.risk_level,
                    resource_scope=resource_scope,
                    command_preview=[f"action={chosen.action}", f"target={_target_name(run)}"],
                    plan_steps=[step.action for step in plan_steps],
                    rollback_plan=["如执行异常，按回滚计划恢复到最近安全点。"],
                    allowed_scopes=risk.allowed_scopes,
                )
            )
            append_audit_event(run_id=recovered.run_id, event_type="APPROVE_CREATED", summary=approval.summary)
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="操作已进入审批门禁，请确认执行范围、计划和回滚方案。",
                    kind="approval",
                    reasoning_summary=_reasoning("系统已恢复出明确意图。", "按风险策略评估为 L2+，因此创建审批交互。", "等待审批通过后再进入执行阶段。"),
                    intent_recovery=run,
                    approval_card=approval.model_dump(),
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        for step in plan_steps:
            append_audit_event(run_id=recovered.run_id, event_type="PRE_EXEC", summary=f"准备执行 {step.action}", step_no=step.seq)
            upsert_checkpoint(run_id=recovered.run_id, step=step, status="waiting")
            upsert_checkpoint(run_id=recovered.run_id, step=step, status="safe")
            append_audit_event(run_id=recovered.run_id, event_type="POST_EXEC", summary=f"已完成 {step.action}", step_no=step.seq)
        append_audit_event(run_id=recovered.run_id, event_type="COMPLETE", summary="执行链路已完成")
        checkpoints = [upsert_checkpoint(run_id=recovered.run_id, step=plan_steps[-1], status="safe")]
        return make_success(
            ChatV2Response(
                session_id=body.session_id,
                message_id=_message_id(),
                assistant_message=f"已按低风险路径完成意图 {chosen.intent_code} 的编排执行。",
                kind="resume",
                reasoning_summary=_reasoning("系统已恢复并确认意图。", "低风险动作直接执行，并写入审计与 checkpoint。", "执行完成，可在 runs 页面查看审计和恢复点。"),
                intent_recovery=run,
                resume_card={
                    "checkpoint_id": checkpoints[-1].checkpoint_id,
                    "run_id": recovered.run_id,
                    "last_safe_step": checkpoints[-1].step_no,
                    "resume_from": f"step {checkpoints[-1].step_no}",
                    "idempotency_key": checkpoints[-1].idempotency_key,
                    "rollback_available": bool(checkpoints[-1].rollback_payload),
                },
                audit_timeline=_audit_timeline(recovered.run_id),
            ).model_dump()
        )
    except Exception as exc:
        return make_error(str(exc))
