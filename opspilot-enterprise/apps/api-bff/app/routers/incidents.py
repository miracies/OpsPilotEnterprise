"""Incident endpoints - proxy to event-ingestion-service."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/incidents", tags=["incidents"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")


@router.get("")
async def list_incidents():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/incidents")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/incidents/{incident_id}")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")


@router.post("/{incident_id}/analyze")
async def analyze_incident(incident_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/incidents/{incident_id}/analyze")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Event ingestion unreachable: {exc}")
