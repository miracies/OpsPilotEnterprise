"""BFF router: executions (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/executions", tags=["executions"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.post("/dry-run")
async def dry_run(body: dict):
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/executions/dry-run", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/submit")
async def submit(body: dict):
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/executions/submit", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("")
async def list_executions(status: str | None = None, limit: int = 50):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/executions", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/{execution_id}")
async def get_execution(execution_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/executions/{execution_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/executions/{execution_id}/cancel", json={})
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
