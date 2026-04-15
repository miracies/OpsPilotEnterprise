"""BFF router: Audit logs (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["audit"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("/audit/logs")
async def list_audit_logs(
    severity: str | None = None,
    event_type: str | None = None,
    actor_type: str | None = None,
    limit: int = 50,
):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            params = {
                "severity": severity,
                "event_type": event_type,
                "actor_type": actor_type,
                "limit": limit,
            }
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/audit/logs", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/audit/logs/{log_id}")
async def get_audit_log(log_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/audit/logs/{log_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/audit/logs")
async def create_audit_log(payload: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/audit/logs", json=payload)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
