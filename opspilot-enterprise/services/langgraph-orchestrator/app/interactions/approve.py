from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from opspilot_schema.interaction import ApprovalCreateRequest, ApprovalDecisionRequest, ApprovalRecord

from app.storage.db import execute, query_one


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def create_approval(body: ApprovalCreateRequest) -> ApprovalRecord:
    if not body.resource_scope.resources:
        raise ValueError("resource scope 未确定，不能进入审批")
    record = ApprovalRecord(
        approval_id=f"ap_{uuid.uuid4().hex[:12]}",
        run_id=body.run_id,
        summary=body.summary,
        domain=body.domain,
        action=body.action,
        risk_level=body.risk_level,
        resource_scope=body.resource_scope,
        command_preview=body.command_preview,
        plan_steps=body.plan_steps,
        rollback_plan=body.rollback_plan,
        allowed_scopes=body.allowed_scopes,
        status="pending",
        expires_at=_expires(body.expires_in_seconds),
        created_at=_now(),
    )
    execute(
        """
        INSERT INTO op_approval_requests(
            approval_id, run_id, risk_level, environment, resource_scope_json, command_preview_json,
            plan_steps_json, rollback_plan_json, allowed_scopes_json, final_scope, decision,
            approved_by, approved_at, expires_at, summary, domain_name, action_name, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?)
        """,
        (
            record.approval_id,
            record.run_id,
            record.risk_level,
            record.resource_scope.environment,
            json.dumps(record.resource_scope.model_dump(), ensure_ascii=False),
            json.dumps(record.command_preview, ensure_ascii=False),
            json.dumps(record.plan_steps, ensure_ascii=False),
            json.dumps(record.rollback_plan, ensure_ascii=False),
            json.dumps(record.allowed_scopes, ensure_ascii=False),
            record.expires_at,
            record.summary,
            record.domain,
            record.action,
            record.created_at,
        ),
    )
    execute(
        """
        INSERT INTO op_interactions(interaction_id, run_id, kind, status, payload_json, response_json, created_by, created_at, expires_at)
        VALUES (?, ?, 'approve', 'pending', ?, NULL, ?, ?, ?)
        """,
        (
            record.approval_id,
            record.run_id,
            json.dumps(record.model_dump(), ensure_ascii=False),
            record.created_by,
            record.created_at,
            record.expires_at,
        ),
    )
    return record


def decide_approval(approval_id: str, body: ApprovalDecisionRequest) -> ApprovalRecord:
    row = query_one("SELECT * FROM op_approval_requests WHERE approval_id=?", (approval_id,))
    if not row:
        raise ValueError(f"Approval {approval_id} not found")
    allowed_scopes = json.loads(row["allowed_scopes_json"] or "[]") or ["once"]
    final_scope = body.scope or allowed_scopes[0]
    if final_scope not in allowed_scopes:
        raise ValueError("审批作用域不合法")
    approved_at = _now()
    execute(
        """
        UPDATE op_approval_requests
        SET decision=?, final_scope=?, approved_by=?, approved_at=?
        WHERE approval_id=?
        """,
        (body.decision, final_scope, body.approved_by, approved_at, approval_id),
    )
    execute(
        """
        UPDATE op_interactions
        SET status=?, response_json=?, responded_by=?, responded_at=?
        WHERE interaction_id=?
        """,
        (
            "approved" if body.decision == "approved" else "rejected",
            json.dumps(
                {
                    "decision": body.decision,
                    "scope": final_scope,
                    "comment": body.comment,
                    "approved_by": body.approved_by,
                    "approved_at": approved_at,
                },
                ensure_ascii=False,
            ),
            body.approved_by,
            approved_at,
            approval_id,
        ),
    )
    updated = query_one("SELECT * FROM op_approval_requests WHERE approval_id=?", (approval_id,))
    return ApprovalRecord(
        approval_id=updated["approval_id"],
        run_id=updated["run_id"],
        summary=updated["summary"],
        domain=updated["domain_name"],
        action=updated["action_name"],
        risk_level=updated["risk_level"],
        resource_scope=json.loads(updated["resource_scope_json"] or "{}"),
        command_preview=json.loads(updated["command_preview_json"] or "[]"),
        plan_steps=json.loads(updated["plan_steps_json"] or "[]"),
        rollback_plan=json.loads(updated["rollback_plan_json"] or "[]"),
        allowed_scopes=allowed_scopes,
        status="approved" if body.decision == "approved" else "rejected",
        decision=body.decision,
        final_scope=final_scope,
        comment=body.comment,
        approved_by=body.approved_by,
        approved_at=approved_at,
        expires_at=updated["expires_at"],
        created_at=updated["created_at"],
    )
