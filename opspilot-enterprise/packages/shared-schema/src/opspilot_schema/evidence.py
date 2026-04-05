from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class Evidence(BaseModel):
    evidence_id: str
    source: str
    source_type: Literal["event", "metric", "log", "topology", "kb", "change", "external_kb"]
    object_type: str
    object_id: str
    timestamp: str
    summary: str
    raw_ref: str | None = None
    confidence: float
    correlation_key: str | None = None


class EvidencePackage(BaseModel):
    package_id: str
    incident_id: str | None = None
    session_id: str | None = None
    evidences: list[Evidence] = []
    created_at: str
