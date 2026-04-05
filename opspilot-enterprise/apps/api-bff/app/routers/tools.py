"""Tool management endpoints - proxy to tool-gateway."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/tools", tags=["tools"])

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")


@router.get("")
async def list_tools():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{TOOL_GATEWAY_URL}/api/v1/tools/")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Tool gateway unreachable: {exc}")


@router.get("/health")
async def tools_health():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{TOOL_GATEWAY_URL}/api/v1/tools/health")
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Tool gateway unreachable: {exc}")
