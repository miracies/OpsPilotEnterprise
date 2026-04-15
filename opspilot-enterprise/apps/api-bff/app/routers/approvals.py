"""BFF router: Approvals (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["approvals"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("/approvals")
async def list_approvals(status: str | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            params = {"status": status} if status else None
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/approvals", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/approvals/{approval_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/approvals/{approval_id}/decide", json=decision)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
