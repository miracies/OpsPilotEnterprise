"""BFF router: monitoring control/status for closed-loop runtime."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("/status")
async def status():
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/monitoring/status")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/start")
async def start():
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/monitoring/start")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/stop")
async def stop():
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/monitoring/stop")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
