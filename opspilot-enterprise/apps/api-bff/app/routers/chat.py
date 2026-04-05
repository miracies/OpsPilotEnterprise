"""Chat session endpoints - proxy to orchestrator."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/chat", tags=["chat"])

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


class CreateSessionBody(BaseModel):
    title: str | None = None


class SendMessageBody(BaseModel):
    message: str


@router.post("/sessions")
async def create_session(body: CreateSessionBody):
    import uuid, datetime
    session = {
        "id": f"sess-{uuid.uuid4().hex[:8]}",
        "title": body.title or "新会话",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tags": [],
        "message_count": 0,
    }
    return make_success(session)


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageBody):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/orchestrate/chat",
                json={"session_id": session_id, "message": body.message},
            )
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Orchestrator unreachable: {exc}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    return make_success({
        "id": session_id,
        "title": "Mock 会话",
        "message_count": 3,
    })


@router.get("/sessions/{session_id}/evidence")
async def get_session_evidence(session_id: str):
    return make_success([])


@router.get("/sessions/{session_id}/tool-traces")
async def get_session_traces(session_id: str):
    return make_success([])
