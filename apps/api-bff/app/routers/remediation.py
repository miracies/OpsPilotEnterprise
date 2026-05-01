"""BFF router: remediation execute proxy."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/remediation", tags=["remediation"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.post("/execute")
async def execute(body: dict):
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/remediation/execute", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
