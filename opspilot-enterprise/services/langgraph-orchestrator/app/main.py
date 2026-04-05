from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from opspilot_schema.change_impact import ChangeImpactRequest
from opspilot_schema.envelope import make_error, make_success

app = FastAPI(title="OpsPilot LangGraph Orchestrator")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8030")
CHANGE_IMPACT_SERVICE_URL = os.environ.get("CHANGE_IMPACT_SERVICE_URL", "http://127.0.0.1:8040")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiagnoseRequest(BaseModel):
    description: str
    object_id: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "healthy"})


@app.post("/api/v1/orchestrate/diagnose")
async def orchestrate_diagnose(body: DiagnoseRequest) -> dict:
    """Simulate diagnosis: would call tool gateway for evidence; returns mock synthesis for now."""
    try:
        _ = TOOL_GATEWAY_URL  # reserved for future httpx integration
        diagnosis_id = f"dg-{uuid.uuid4().hex[:12]}"
        data = {
            "diagnosis_id": diagnosis_id,
            "description": body.description,
            "object_id": body.object_id,
            "root_cause_candidates": [
                {
                    "id": "rc-1",
                    "description": "Suspected dependency timeout after latest deploy",
                    "confidence": 0.68,
                    "category": "deployment",
                },
                {
                    "id": "rc-2",
                    "description": "Database connection pool saturation under load",
                    "confidence": 0.52,
                    "category": "database",
                },
            ],
            "evidence_refs": ["ev-agg-1", "ev-log-2", "ev-metric-3"],
            "recommended_actions": [
                "Scale checkout replicas +2 and watch p95",
                "Enable temporary circuit breaker on payments client",
                "Capture thread dumps from checkout pods",
            ],
            "tool_gateway_url": TOOL_GATEWAY_URL,
            "simulated_at": _now(),
        }
        return make_success(data)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/orchestrate/change-impact")
async def orchestrate_change_impact(body: ChangeImpactRequest) -> dict:
    url = f"{CHANGE_IMPACT_SERVICE_URL.rstrip('/')}/api/v1/change-impact/analyze"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body.model_dump())
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        return make_error(f"change-impact request failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/orchestrate/chat")
async def orchestrate_chat(body: ChatRequest) -> dict:
    try:
        reply = (
            f"[mock] Acknowledged message in session {body.session_id!r}. "
            "Next: correlate recent deploys with error budget burn."
        )
        data = {
            "session_id": body.session_id,
            "assistant_message": reply,
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        }
        return make_success(data)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))
