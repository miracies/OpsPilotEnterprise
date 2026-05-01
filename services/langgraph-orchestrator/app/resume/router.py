from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success
from opspilot_schema.resume import ResumeRequest

from .service import resume_run

router = APIRouter(prefix="/api/v1/runs", tags=["resume"])


@router.post("/{run_id}/resume")
async def resume_route(run_id: str, body: ResumeRequest):
    result = resume_run(run_id, body)
    return make_success(result.model_dump())
