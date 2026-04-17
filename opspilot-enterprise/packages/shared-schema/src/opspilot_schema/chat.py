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


class ProgressEvent(BaseModel):
    stage: Literal[
        "received",
        "intent_parsed",
        "agent_selected",
        "tool_invoking",
        "tool_done",
        "tool_error",
        "completed",
        "failed",
    ]
    text: str
    ts: str
    status: Literal["in_progress", "success", "error"]
    tool_name: str | None = None
    agent_name: str | None = None


class ReasoningSummary(BaseModel):
    intent_understanding: str
    execution_plan: str
    result_summary: str


class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    tool_traces: list[ToolTrace] | None = None
    evidence_refs: list[str] | None = None
    root_cause: dict | None = None
    root_cause_candidates: list[dict] | None = None
    hypotheses: list[dict] | None = None
    winning_hypothesis: dict | None = None
    counter_evidence_result: dict | None = None
    conclusion_status: Literal["confirmed", "probable", "insufficient_evidence", "contradicted"] | None = None
    evidence_sufficiency: dict | None = None
    contradictions: list[dict] | None = None
    recommended_actions: list[str] | None = None
    agent_name: str | None = None
    export_file: dict | None = None
    export_columns: list[str] | None = None
    ignored_columns: list[str] | None = None
    status: Literal["in_progress", "completed", "failed"] | None = None
    progress_events: list[ProgressEvent] | None = None
    reasoning_summary: ReasoningSummary | None = None
    analysis_steps: list[dict] | None = None
