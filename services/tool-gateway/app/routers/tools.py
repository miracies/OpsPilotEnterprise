from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import registry
from opspilot_schema import ToolHealthStatus, make_error, make_success

router = APIRouter(prefix="/tools")


@router.get("/")
def list_registered_tools() -> dict:
    return make_success(
        data=registry.list_tools(),
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )


@router.get("/health")
def tools_health() -> dict:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    statuses = [
        ToolHealthStatus(
            name=t["name"],
            provider=t["provider"],
            healthy=True,
            last_check=now,
            latency_ms=12 + i * 3,
        ).model_dump()
        for i, t in enumerate(registry.list_tools())
    ]
    return make_success(
        data=statuses,
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )


@router.get("/{name}", response_model=None)
def get_tool(name: str) -> dict | JSONResponse:
    tool = registry.get_tool(name)
    if tool is None:
        return JSONResponse(
            status_code=404,
            content=make_error(
                error=f"tool not found: {name}",
                request_id=str(uuid4()),
                trace_id=str(uuid4()),
            ),
        )
    return make_success(
        data=tool,
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )


@router.post("/register", response_model=None)
def register_tool(meta: dict[str, Any]) -> dict | JSONResponse:
    try:
        registered = registry.register_tool(meta)
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=make_error(
                error=str(e),
                request_id=str(uuid4()),
                trace_id=str(uuid4()),
            ),
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=make_error(
                error=str(e),
                request_id=str(uuid4()),
                trace_id=str(uuid4()),
            ),
        )
    return make_success(
        data={"registered": True, "tool": registered},
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )


@router.post("/unregister", response_model=None)
def unregister_tool(body: dict[str, Any]) -> dict | JSONResponse:
    name = body.get("name")
    if not name or not isinstance(name, str):
        return JSONResponse(
            status_code=400,
            content=make_error(
                error='missing or invalid "name"',
                request_id=str(uuid4()),
                trace_id=str(uuid4()),
            ),
        )
    removed = registry.unregister_tool(name)
    if not removed:
        return JSONResponse(
            status_code=404,
            content=make_error(
                error=f"tool not found: {name}",
                request_id=str(uuid4()),
                trace_id=str(uuid4()),
            ),
        )
    return make_success(
        data={"unregistered": True, "name": name},
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )
