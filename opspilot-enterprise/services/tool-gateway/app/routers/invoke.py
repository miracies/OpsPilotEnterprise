from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from opspilot_schema import make_error, make_success

router = APIRouter(prefix="/invoke")

VMWARE_GATEWAY_URL = os.environ.get("VMWARE_GATEWAY_URL", "http://localhost:8030")
CHANGE_IMPACT_URL = os.environ.get("CHANGE_IMPACT_URL", "http://localhost:8040")


class InvokeBody(BaseModel):
    input: Any = Field(default_factory=dict)
    dry_run: bool = False


@router.post("/{tool_name}")
async def invoke_tool(tool_name: str, body: InvokeBody, response: Response) -> dict:
    request_id = str(uuid4())
    trace_id = str(uuid4())
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Trace-Id"] = trace_id

    payload = {"input": body.input, "dry_run": body.dry_run}
    safe_path = quote(tool_name, safe="")

    if tool_name.startswith("vmware."):
        url = f"{VMWARE_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{safe_path}"
        return await _forward_or_fail(url, payload, request_id, trace_id)

    if tool_name.startswith("change_impact."):
        url = f"{CHANGE_IMPACT_URL.rstrip('/')}/api/v1/invoke/{safe_path}"
        return await _forward_or_fail(url, payload, request_id, trace_id)

    data = {
        "tool": tool_name,
        "input": body.input,
        "dry_run": body.dry_run,
        "mock": True,
    }
    return make_success(data=data, request_id=request_id, trace_id=trace_id)


async def _forward_or_fail(
    url: str,
    payload: dict[str, Any],
    request_id: str,
    trace_id: str,
) -> dict:
    headers = {
        "X-Request-Id": request_id,
        "X-Trace-Id": trace_id,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        return make_error(
            error=f"upstream request failed: {e}",
            request_id=request_id,
            trace_id=trace_id,
        )

    try:
        body = r.json()
    except ValueError:
        return make_error(
            error=f"upstream returned non-JSON (status {r.status_code})",
            request_id=request_id,
            trace_id=trace_id,
        )

    if isinstance(body, dict) and all(
        k in body for k in ("request_id", "success", "message", "timestamp")
    ):
        body = {**body, "request_id": request_id, "trace_id": trace_id}
        return body

    if r.is_success:
        return make_success(
            data=body if body is not None else {},
            request_id=request_id,
            trace_id=trace_id,
        )

    return make_error(
        error=body.get("error") if isinstance(body, dict) else str(body),
        request_id=request_id,
        trace_id=trace_id,
    )
