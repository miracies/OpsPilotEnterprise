from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/runs", tags=["runs"])
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


@router.get("/{run_id}/audit")
async def get_run_audit(run_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/v1/runs/{run_id}/audit")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")


@router.post("/{run_id}/resume")
async def resume_run(run_id: str, body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/runs/{run_id}/resume", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")
