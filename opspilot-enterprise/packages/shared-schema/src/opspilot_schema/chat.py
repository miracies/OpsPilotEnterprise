from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class ToolTrace(BaseModel):
    tool_name: str
    gateway: str
    input_summary: str
    output_summary: str
    duration_ms: int
    status: Literal["success", "error", "denied"]
    timestamp: str


class ChatSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    tags: list[str] = []
    message_count: int = 0


class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    tool_traces: list[ToolTrace] | None = None
    evidence_refs: list[str] | None = None
    root_cause_candidates: list[dict] | None = None
    recommended_actions: list[str] | None = None
    agent_name: str | None = None
