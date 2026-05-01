from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success
from opspilot_schema.intent import IntentAnalyzeInput, IntentRecoverInput

from app.audit.events import append_audit_event
from .analyze_service import analyze_intent
from .service import recover

router = APIRouter(prefix="/api/v1/intent", tags=["intent-recovery"])


@router.post("/recover")
async def recover_intent(body: IntentRecoverInput):
    run = recover(body)
    return make_success(run.model_dump())


@router.post("/analyze")
async def analyze_intent_route(body: IntentAnalyzeInput):
    result = analyze_intent(body)
    append_audit_event(run_id=result.run_id, event_type="CONTEXT_COMPLETED", summary="Context completion finished")
    append_audit_event(run_id=result.run_id, event_type="NORMALIZED", summary=f"Normalized utterance: {result.normalized_utterance[:80]}")
    append_audit_event(run_id=result.run_id, event_type="DISAMBIGUATED", summary=f"Intent decision: {result.decision}")
    append_audit_event(
        run_id=result.run_id,
        event_type="EXECUTION_INTENT_SET",
        summary=f"Execution intent mode={result.execution_intent.mode}",
    )
    if result.memory_refs:
        append_audit_event(run_id=result.run_id, event_type="MEMORY_HIT", summary=f"Memory refs={len(result.memory_refs)}")
    return make_success(result.model_dump())
