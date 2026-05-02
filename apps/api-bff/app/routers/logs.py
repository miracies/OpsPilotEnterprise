"""BFF router: logs (proxy to log-gateway)."""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Request

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/logs", tags=["logs"])

LOG_GATEWAY_URL = os.environ.get("LOG_GATEWAY_URL", "http://127.0.0.1:8055").rstrip("/")


async def _proxy(method: str, path: str, *, json_body: Any = None, timeout: float = 60.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, f"{LOG_GATEWAY_URL}{path}", json=json_body)
    return resp.json()


@router.get("/sources")
async def list_sources() -> dict:
    try:
        return await _proxy("GET", "/api/v1/logs/sources")
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.post("/sources")
async def upsert_source(body: dict) -> dict:
    try:
        return await _proxy("POST", "/api/v1/logs/sources", json_body=body)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str) -> dict:
    try:
        return await _proxy("DELETE", f"/api/v1/logs/sources/{source_id}")
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.post("/sources/test")
async def test_source(body: dict) -> dict:
    try:
        return await _proxy("POST", "/api/v1/logs/sources/test", json_body=body)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.post("/search")
async def search_logs(body: dict) -> dict:
    try:
        return await _proxy("POST", "/api/v1/logs/search", json_body=body, timeout=90.0)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.post("/context")
async def context_logs(body: dict) -> dict:
    try:
        return await _proxy("POST", "/api/v1/logs/context", json_body=body, timeout=90.0)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.get("/raw/{log_id:path}")
async def get_raw(log_id: str) -> dict:
    try:
        return await _proxy("GET", f"/api/v1/logs/raw/{log_id}", timeout=60.0)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")


@router.post("/evidence")
async def add_log_evidence(body: dict) -> dict:
    try:
        return await _proxy("POST", "/api/v1/logs/evidence", json_body=body)
    except httpx.HTTPError as exc:
        return make_error(f"Log gateway unreachable: {exc}")
