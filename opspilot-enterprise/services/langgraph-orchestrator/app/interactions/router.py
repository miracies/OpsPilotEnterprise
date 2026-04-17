from __future__ import annotations

import json

from fastapi import APIRouter

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.intent import IntentRecoverInput
from opspilot_schema.interaction import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ClarifyAnswerRequest,
    ClarifyCreateRequest,
    ResourceRef,
    ResourceScope,
)
from opspilot_schema.policy_rule import RiskEvaluationInput
from opspilot_schema.resume import PlanStep

from app.audit.checkpoint import upsert_checkpoint
from app.audit.events import append_audit_event
from app.audit.router import get_run_audit
from app.intent_recovery.service import recover
from app.policy.engine import evaluate as evaluate_risk
from app.storage.db import query_one

from .approve import create_approval, decide_approval
from .clarify import answer_clarify, create_clarify

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])


def _resource_scope_from_run(run: dict) -> ResourceScope:
    chosen = run.get("chosen_intent") or {}
    env = chosen.get("environment") or chosen.get("inferred_environment") or "prod"
    target = None
    for slot in chosen.get("slots") or []:
        if slot.get("name") == "target_object":
            target = slot.get("value")
            break
    if not target:
        return ResourceScope(environment=env, resources=[])
    return ResourceScope(
        environment=env,
        resources=[ResourceRef(type=chosen.get("domain") or "resource", id=str(target), name=str(target))],
    )


def _plan_steps_from_approval_row(row: dict) -> list[PlanStep]:
    action = str(row.get("action_name") or "execute")
    steps = json.loads(row.get("plan_steps_json") or "[]")
    if steps:
        return [PlanStep(seq=idx, action=str(step), args={"approval_id": row["approval_id"]}) for idx, step in enumerate(steps, 1)]
    return [PlanStep(seq=1, action=action, args={"approval_id": row["approval_id"]})]


@router.post("/clarify")
async def create_clarify_interaction(body: ClarifyCreateRequest):
    record = create_clarify(body)
    append_audit_event(run_id=body.run_id, event_type="CLARIFY_CREATED", summary=body.question)
    return make_success(record.model_dump())


@router.post("/clarify/{interaction_id}/answer")
async def answer_clarify_interaction(interaction_id: str, body: ClarifyAnswerRequest):
    try:
        record = answer_clarify(interaction_id, body)
    except ValueError as exc:
        return make_error(str(exc))

    append_audit_event(
        run_id=record.run_id,
        event_type="CLARIFY_ANSWERED",
        summary=f"已回答澄清: {record.selected_choice or record.free_text or 'free_text'}",
        actor_type="user",
        actor_id=record.responded_by or "user",
    )

    run_row = query_one("SELECT * FROM op_intent_runs WHERE run_id=?", (record.run_id,))
    if not run_row:
        return make_success({**record.model_dump(), "next_action": "none"})

    patched_utterance = " ".join(
        part for part in [run_row.get("raw_utterance", ""), record.selected_choice or "", record.free_text or ""] if part
    )
    rerun = recover(
        IntentRecoverInput(
            conversation_id=str(run_row.get("conversation_id") or ""),
            user_id=str(run_row.get("user_id") or "web-user"),
            channel=str(run_row.get("channel") or "web"),
            utterance=patched_utterance,
            tenant_id=run_row.get("tenant_id"),
        )
    )
    append_audit_event(run_id=rerun.run_id, event_type="RECOVER", summary=f"Clarify后重跑恢复: {rerun.decision}")
    run_data = rerun.model_dump()

    if rerun.decision != "recovered":
        question = "请继续补充关键信息。" if rerun.missing_slots else "候选意图仍有歧义，请再次确认。"
        clarify_next = create_clarify(
            ClarifyCreateRequest(
                run_id=rerun.run_id,
                question=question,
                choices=[],
                allow_free_text=True,
                reason_code="missing_slot" if rerun.missing_slots else "ambiguous_intent",
            )
        )
        append_audit_event(run_id=rerun.run_id, event_type="CLARIFY_CREATED", summary=question)
        return make_success(
            {
                **record.model_dump(),
                "next_action": "clarify_pending",
                "next_message": question,
                "intent_recovery": run_data,
                "clarify_card": clarify_next.model_dump(),
                "audit_timeline": (await get_run_audit(rerun.run_id)).get("data", {}),
            }
        )

    chosen = rerun.chosen_intent
    assert chosen is not None
    risk = evaluate_risk(
        RiskEvaluationInput(
            domain=chosen.domain,
            action=chosen.action,
            environment=(chosen.environment or chosen.inferred_environment or "prod"),
            resource_scope=chosen.resource_scope,
        )
    )

    if risk.require_approval:
        scope = _resource_scope_from_run(run_data)
        approval = create_approval(
            ApprovalCreateRequest(
                run_id=rerun.run_id,
                summary=f"对 {scope.resources[0].name if scope.resources else '目标对象'} 执行 {chosen.action}",
                domain=chosen.domain,
                action=chosen.action,
                risk_level=risk.risk_level,
                resource_scope=scope,
                command_preview=[f"action={chosen.action}"],
                plan_steps=[chosen.action],
                rollback_plan=["执行异常时回滚到最近安全点"],
                allowed_scopes=risk.allowed_scopes,
            )
        )
        append_audit_event(run_id=rerun.run_id, event_type="APPROVE_CREATED", summary=approval.summary)
        return make_success(
            {
                **record.model_dump(),
                "next_action": "approval_pending",
                "next_message": "澄清完成，已进入审批门禁。",
                "intent_recovery": run_data,
                "approval_card": approval.model_dump(),
                "audit_timeline": (await get_run_audit(rerun.run_id)).get("data", {}),
            }
        )

    return make_success(
        {
            **record.model_dump(),
            "next_action": "recovered",
            "next_message": "澄清完成，意图恢复成功。",
            "intent_recovery": run_data,
            "audit_timeline": (await get_run_audit(rerun.run_id)).get("data", {}),
        }
    )


@router.post("/approve")
async def create_approval_interaction(body: ApprovalCreateRequest):
    try:
        record = create_approval(body)
    except ValueError as exc:
        return make_error(str(exc))
    append_audit_event(run_id=body.run_id, event_type="APPROVE_CREATED", summary=body.summary)
    return make_success(record.model_dump())


@router.post("/approve/{approval_id}/decision")
async def decide_approval_interaction(approval_id: str, body: ApprovalDecisionRequest):
    try:
        record = decide_approval(approval_id, body)
    except ValueError as exc:
        return make_error(str(exc))

    append_audit_event(
        run_id=record.run_id,
        event_type="APPROVE_DECIDED",
        summary=f"审批{record.decision}",
        actor_type="user",
        actor_id=record.approved_by or body.approved_by,
    )

    if body.decision != "approved":
        return make_success({**record.model_dump(), "next_action": "stop"})

    approval_row = query_one("SELECT * FROM op_approval_requests WHERE approval_id=?", (approval_id,))
    if not approval_row:
        return make_success({**record.model_dump(), "next_action": "start-execution"})

    steps = _plan_steps_from_approval_row(approval_row)
    last_checkpoint = None
    for step in steps:
        append_audit_event(run_id=record.run_id, event_type="PRE_EXEC", summary=f"准备执行 {step.action}", step_no=step.seq)
        upsert_checkpoint(run_id=record.run_id, step=step, status="waiting")
        last_checkpoint = upsert_checkpoint(run_id=record.run_id, step=step, status="safe")
        append_audit_event(run_id=record.run_id, event_type="POST_EXEC", summary=f"已完成 {step.action}", step_no=step.seq)

    append_audit_event(run_id=record.run_id, event_type="COMPLETE", summary="审批通过后自动推进执行完成")

    resume_card = None
    if last_checkpoint:
        resume_card = {
            "checkpoint_id": last_checkpoint.checkpoint_id,
            "run_id": record.run_id,
            "last_safe_step": last_checkpoint.step_no,
            "resume_from": f"step {last_checkpoint.step_no}",
            "idempotency_key": last_checkpoint.idempotency_key,
            "rollback_available": bool(last_checkpoint.rollback_payload),
        }

    return make_success(
        {
            **record.model_dump(),
            "next_action": "executed",
            "next_message": "审批已通过，系统已自动推进执行并完成审计记录。",
            "resume_card": resume_card,
            "audit_timeline": (await get_run_audit(record.run_id)).get("data", {}),
        }
    )
