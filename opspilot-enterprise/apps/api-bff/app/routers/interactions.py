from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/interactions", tags=["interactions"])
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


@router.post("/clarify")
async def create_clarify(body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/interactions/clarify", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")


@router.post("/clarify/{interaction_id}/answer")
async def answer_clarify(interaction_id: str, body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/interactions/clarify/{interaction_id}/answer", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")


@router.post("/approve")
async def create_approve(body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/interactions/approve", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")


@router.post("/approve/{approval_id}/decision")
async def decide_approve(approval_id: str, body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/api/v1/interactions/approve/{approval_id}/decision", json=body)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")
