from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/intent", tags=["intent"])
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


@router.post("/recover")
async def recover_intent(body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/intent/recover", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")
