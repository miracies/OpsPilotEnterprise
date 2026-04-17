from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success
from opspilot_schema.intent import IntentRecoverInput

from .service import recover

router = APIRouter(prefix="/api/v1/intent", tags=["intent-recovery"])


@router.post("/recover")
async def recover_intent(body: IntentRecoverInput):
    run = recover(body)
    return make_success(run.model_dump())
