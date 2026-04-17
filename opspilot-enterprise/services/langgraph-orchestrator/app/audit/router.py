from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success

from .events import list_audit_events

router = APIRouter(prefix="/api/v1/runs", tags=["audit"])


@router.get("/{run_id}/audit")
async def get_run_audit(run_id: str):
    events = list_audit_events(run_id)
    decision_chain = [event.summary for event in events if event.event_type in {"RECOVER", "CLARIFY_CREATED", "APPROVE_CREATED", "APPROVE_DECIDED", "RESUME"}]
    tool_outputs = [event.summary for event in events if event.event_type in {"PRE_EXEC", "POST_EXEC", "ROLLBACK"}]
    return make_success(
        {
            "run_id": run_id,
            "operator": "orchestrator",
            "decision_chain": decision_chain,
            "tool_outputs": tool_outputs,
            "events": [event.model_dump() for event in events],
        }
    )
