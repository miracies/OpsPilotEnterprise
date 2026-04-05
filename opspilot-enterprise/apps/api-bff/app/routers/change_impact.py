"""Change impact endpoints - proxy to orchestrator."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_success, make_error
from opspilot_schema.change_impact import ChangeImpactRequest

router = APIRouter(prefix="/change-impact", tags=["change-impact"])

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


@router.post("/analyze")
async def analyze_change_impact(body: ChangeImpactRequest):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/orchestrate/change-impact",
                json=body.model_dump(),
            )
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")
