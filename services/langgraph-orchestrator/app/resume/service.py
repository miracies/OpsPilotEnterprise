from __future__ import annotations

from opspilot_schema.resume import ResumeRequest, ResumeResponse

from app.audit.checkpoint import list_checkpoints
from app.audit.events import append_audit_event, list_audit_events


def resume_run(run_id: str, body: ResumeRequest) -> ResumeResponse:
    checkpoints = list_checkpoints(run_id)
    if not checkpoints:
        return ResumeResponse(
            run_id=run_id,
            status="nothing_to_resume",
            message="没有找到可恢复的执行断点。",
            rollback_available=False,
        )
    safe_steps = [checkpoint.step_no for checkpoint in checkpoints if checkpoint.status == "safe"]
    candidates = [checkpoint for checkpoint in checkpoints if checkpoint.status in {"waiting", "failed"}]
    if body.mode == "rollback":
        append_audit_event(run_id=run_id, event_type="ROLLBACK", summary="用户选择从最近安全点回滚")
        return ResumeResponse(
            run_id=run_id,
            status="rolled_back",
            resume_from_step=safe_steps[-1] if safe_steps else None,
            skipped_steps=safe_steps,
            message="已记录回滚请求。",
            last_safe_step=safe_steps[-1] if safe_steps else None,
            resume_from="rollback",
            rollback_available=True,
            decision_chain=[event.summary for event in list_audit_events(run_id)],
            tool_outputs=[f"rollback checkpoint={checkpoints[-1].checkpoint_id}"],
        )
    if not candidates:
        return ResumeResponse(
            run_id=run_id,
            status="nothing_to_resume",
            skipped_steps=safe_steps,
            message="所有步骤都已处于安全完成状态，无需 resume。",
            last_safe_step=safe_steps[-1] if safe_steps else None,
            rollback_available=bool(safe_steps),
            decision_chain=[event.summary for event in list_audit_events(run_id)],
            tool_outputs=[],
        )
    target = candidates[0]
    append_audit_event(run_id=run_id, event_type="RESUME", summary=f"从 step {target.step_no} 继续执行")
    return ResumeResponse(
        run_id=run_id,
        status="resumed",
        resume_from_step=target.step_no,
        skipped_steps=safe_steps,
        message=f"已从 step {target.step_no} 继续。",
        last_safe_step=safe_steps[-1] if safe_steps else None,
        resume_from=f"step {target.step_no}",
        rollback_available=bool(target.rollback_payload),
        decision_chain=[event.summary for event in list_audit_events(run_id)],
        tool_outputs=[f"resume checkpoint={target.checkpoint_id}"],
    )
