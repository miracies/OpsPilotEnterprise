"""BFF router: Case archive (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["cases"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("/cases")
async def list_cases(category: str | None = None, status: str | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            params = {"category": category, "status": status}
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/cases", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/cases/{case_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
