from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class AffectedObject(BaseModel):
    object_type: str
    object_id: str
    object_name: str


class RootCauseCandidate(BaseModel):
    id: str
    description: str
    confidence: float
    evidence_refs: list[str] = []
    category: str


class Incident(BaseModel):
    id: str
    title: str
    status: Literal["new", "analyzing", "pending_action", "resolved", "archived"]
    severity: Literal["critical", "high", "medium", "low", "info"]
    source: str
    source_type: str
    affected_objects: list[AffectedObject] = []
    first_seen_at: str
    last_updated_at: str
    owner: str | None = None
    ai_analysis_triggered: bool = False
    root_cause_candidates: list[RootCauseCandidate] = []
    recommended_actions: list[str] = []
    evidence_refs: list[str] = []
    summary: str


class IncidentTimelineEntry(BaseModel):
    timestamp: str
    type: Literal["event", "analysis", "notification", "action", "resolution"]
    summary: str
    agent: str | None = None
    detail: str | None = None
