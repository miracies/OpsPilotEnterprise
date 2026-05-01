"""BFF router: evidence (proxy to evidence-aggregator)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/evidence", tags=["evidence"])

EVIDENCE_AGGREGATOR_URL = os.environ.get("EVIDENCE_AGGREGATOR_URL", "http://127.0.0.1:8050")


@router.post("/aggregate")
async def aggregate(body: dict):
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(f"{EVIDENCE_AGGREGATOR_URL}/api/v1/evidence/aggregate", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Evidence aggregator unreachable: {exc}")


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{EVIDENCE_AGGREGATOR_URL}/api/v1/evidence/{evidence_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Evidence aggregator unreachable: {exc}")

