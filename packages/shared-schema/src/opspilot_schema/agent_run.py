from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AgentRunStep(BaseModel):
    step_id: str
    agent_name: str
    status: str
    input_summary: str
    output_summary: Optional[str] = None
    tool_calls: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class AgentRun(BaseModel):
    id: str
    intent: str
    status: str
    trigger: str
    incident_ref: Optional[str] = None
    session_ref: Optional[str] = None
    steps: list[AgentRunStep] = []
    total_tool_calls: int = 0
    total_duration_ms: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None
