from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


EvidenceSourceType = Literal["event", "metric", "log", "topology", "kb", "change", "external_kb", "detail", "alert"]


class Evidence(BaseModel):
    evidence_id: str
    source: str
    source_type: EvidenceSourceType
    object_type: str
    object_id: str
    timestamp: str
    summary: str
    raw_ref: str | None = None
    confidence: float
    correlation_key: str | None = None


class EvidenceSourceStats(BaseModel):
    source_type: EvidenceSourceType
    count: int
    avg_confidence: float


class EvidenceCoverage(BaseModel):
    requested_sources: int
    collected_sources: int
    missing_sources: int
    required_evidence_types: list[str] = []
    present_evidence_types: list[str] = []
    missing_critical_evidence: list[str] = []
    sufficiency_score: float = 0.0
    freshness_score: float = 0.0


class EvidenceError(BaseModel):
    source: str
    message: str


class EvidenceContradiction(BaseModel):
    type: str
    summary: str
    evidence_refs: list[str] = []
    severity: Literal["high", "medium", "low"] = "medium"


class EvidencePackage(BaseModel):
    package_id: str
    incident_id: str | None = None
    session_id: str | None = None
    evidences: list[Evidence] = []
    created_at: str
    source_stats: list[EvidenceSourceStats] = []
    coverage: EvidenceCoverage | None = None
    errors: list[EvidenceError] = []
    required_evidence_types: list[str] = []
    present_evidence_types: list[str] = []
    missing_critical_evidence: list[str] = []
    sufficiency_score: float = 0.0
    freshness_score: float = 0.0
    contradictions: list[EvidenceContradiction] = []
