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


class RootCause(BaseModel):
    summary: str
    confidence: float
    evidence_refs: list[str] = []


class EvidenceSufficiency(BaseModel):
    required_evidence_types: list[str] = []
    present_evidence_types: list[str] = []
    missing_critical_evidence: list[str] = []
    sufficiency_score: float = 0.0
    freshness_score: float = 0.0


class Hypothesis(BaseModel):
    id: str
    summary: str
    category: str
    confidence: float
    support_evidence_refs: list[str] = []
    counter_evidence_refs: list[str] = []
    missing_evidence: list[str] = []
    status: Literal["candidate", "confirmed", "probable", "refuted", "inconclusive"] = "candidate"
    why: str = ""


class CounterEvidenceResult(BaseModel):
    status: Literal["refuted", "not_refuted", "inconclusive"]
    checked_hypothesis_id: str | None = None
    summary: str
    evidence_refs: list[str] = []


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
    root_cause: RootCause | None = None
    root_cause_candidates: list[RootCauseCandidate] = []
    hypotheses: list[Hypothesis] = []
    winning_hypothesis: Hypothesis | None = None
    counter_evidence_result: CounterEvidenceResult | None = None
    conclusion_status: Literal["confirmed", "probable", "insufficient_evidence", "contradicted"] | None = None
    evidence_sufficiency: EvidenceSufficiency | None = None
    contradictions: list[dict] = []
    recommended_actions: list[str] = []
    evidence_refs: list[str] = []
    summary: str


class IncidentTimelineEntry(BaseModel):
    timestamp: str
    type: Literal["event", "analysis", "notification", "action", "resolution"]
    summary: str
    agent: str | None = None
    detail: str | None = None
