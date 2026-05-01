"""BFF router: Notifications & On-call (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["notifications"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("/notifications")
async def list_notifications(status: str | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            params = {"status": status} if status else None
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/notifications", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(notification_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/notifications/{notification_id}/acknowledge")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/oncall/shifts")
async def list_oncall_shifts():
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/oncall/shifts")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
