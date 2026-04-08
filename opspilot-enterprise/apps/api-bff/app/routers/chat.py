"""Chat session endpoints - proxy to orchestrator with in-memory session store."""
from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/chat", tags=["chat"])

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── In-memory session store ──────────────────────────────────
_sessions: dict[str, dict] = {}
_messages: dict[str, list[dict]] = defaultdict(list)
_evidences: dict[str, list[dict]] = defaultdict(list)
_tool_traces: dict[str, list[dict]] = defaultdict(list)
_diagnoses: dict[str, dict] = {}  # diagnosis_id -> full diagnosis data


class CreateSessionBody(BaseModel):
    title: str | None = None


class SendMessageBody(BaseModel):
    message: str


@router.get("/sessions")
async def list_sessions():
    sessions = sorted(_sessions.values(), key=lambda s: s["updated_at"], reverse=True)
    return make_success(sessions)


@router.post("/sessions")
async def create_session(body: CreateSessionBody):
    sid = f"sess-{uuid.uuid4().hex[:8]}"
    now = _now()
    session = {
        "id": sid,
        "title": body.title or "新会话",
        "created_at": now,
        "updated_at": now,
        "tags": [],
        "message_count": 0,
    }
    _sessions[sid] = session
    return make_success(session)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        return make_success({
            "id": session_id,
            "title": "未知会话",
            "message_count": 0,
        })
    return make_success(session)


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    return make_success(_messages.get(session_id, []))


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageBody):
    # Ensure session exists
    if session_id not in _sessions:
        now = _now()
        _sessions[session_id] = {
            "id": session_id,
            "title": body.message[:30],
            "created_at": now,
            "updated_at": now,
            "tags": [],
            "message_count": 0,
        }

    # Store user message
    user_msg = {
        "id": f"msg-{uuid.uuid4().hex[:10]}",
        "session_id": session_id,
        "role": "user",
        "content": body.message,
        "timestamp": _now(),
    }
    _messages[session_id].append(user_msg)

    # Build conversation history for LLM context
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in _messages[session_id]
        if m["role"] in ("user", "assistant")
    ]

    # Call orchestrator (with local fallback)
    orch_result = None
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/orchestrate/chat",
                json={"session_id": session_id, "message": body.message, "history": history},
            )
            orch_result = resp.json()
        except Exception:
            pass

    if not orch_result or not orch_result.get("success"):
        import re
        _diag_kw = re.compile(r"分析|诊断|排查|告警|根因|异常|故障|排障|为什么|原因|检查")
        is_diag = bool(_diag_kw.search(body.message))
        fallback_data = {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": f"[本地模式] 收到：「{body.message}」",
            "agent_name": "RCAAgent" if is_diag else "Orchestrator",
            "tool_traces": [
                {"tool_name": "vmware.get_host_detail", "gateway": "vmware-skill-gateway",
                 "input_summary": '{"host_id":"host-33"}', "output_summary": "CPU: 97.3%",
                 "duration_ms": 320, "status": "success", "timestamp": _now()},
            ] if is_diag else [],
            "evidence_refs": ["ev-fallback-1"] if is_diag else [],
            "evidences": [
                {"evidence_id": "ev-fallback-1", "source_type": "metric",
                 "summary": "CPU 97.3% (fallback)", "confidence": 0.9, "timestamp": _now()},
            ] if is_diag else [],
            "root_cause_candidates": [
                {"description": "Fallback diagnosis", "confidence": 0.85, "category": "unknown"},
            ] if is_diag else None,
            "recommended_actions": ["检查主机指标"] if is_diag else None,
            "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}" if is_diag else None,
        }
        data = fallback_data
    else:
        data = orch_result["data"]

    # Build assistant message
    assistant_msg: dict = {
        "id": data.get("message_id", f"msg-{uuid.uuid4().hex[:10]}"),
        "session_id": session_id,
        "role": "assistant",
        "content": data.get("assistant_message", ""),
        "timestamp": _now(),
        "agent_name": data.get("agent_name"),
        "tool_traces": data.get("tool_traces", []),
        "evidence_refs": data.get("evidence_refs", []),
        "root_cause_candidates": data.get("root_cause_candidates"),
        "recommended_actions": data.get("recommended_actions"),
        "diagnosis_id": data.get("diagnosis_id"),
    }
    _messages[session_id].append(assistant_msg)

    # Store evidence & tool traces at session level
    for ev in data.get("evidences", []):
        if not any(e["evidence_id"] == ev["evidence_id"] for e in _evidences[session_id]):
            _evidences[session_id].append(ev)

    for tt in data.get("tool_traces", []):
        _tool_traces[session_id].append(tt)

    # Store diagnosis if present
    diag_id = data.get("diagnosis_id")
    if diag_id:
        _diagnoses[diag_id] = {
            "diagnosis_id": diag_id,
            "session_id": session_id,
            "description": body.message,
            "assistant_message": data.get("assistant_message", ""),
            "root_cause_candidates": data.get("root_cause_candidates", []),
            "evidence_refs": data.get("evidence_refs", []),
            "evidences": data.get("evidences", []),
            "recommended_actions": data.get("recommended_actions", []),
            "tool_traces": data.get("tool_traces", []),
            "created_at": _now(),
        }

    # Update session metadata
    _sessions[session_id]["updated_at"] = _now()
    _sessions[session_id]["message_count"] = len(_messages[session_id])
    if _sessions[session_id]["title"] == "新会话" or _sessions[session_id]["title"] == body.message[:30]:
        _sessions[session_id]["title"] = body.message[:30]

    return make_success(assistant_msg)


@router.get("/sessions/{session_id}/evidence")
async def get_session_evidence(session_id: str):
    return make_success(_evidences.get(session_id, []))


@router.get("/sessions/{session_id}/tool-traces")
async def get_session_traces(session_id: str):
    return make_success(_tool_traces.get(session_id, []))


@router.get("/diagnoses/{diagnosis_id}")
async def get_diagnosis(diagnosis_id: str):
    diag = _diagnoses.get(diagnosis_id)
    if not diag:
        return make_error(f"Diagnosis {diagnosis_id} not found")
    return make_success(diag)
