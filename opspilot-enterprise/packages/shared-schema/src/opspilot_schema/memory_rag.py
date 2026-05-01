from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MemoryScope = Literal["session", "user", "org", "execution"]
PiiLevel = Literal["none", "low", "medium", "high"]


class MemoryUpsertRequest(BaseModel):
    tenant_id: str
    scope: MemoryScope
    subject_id: str
    key: str
    value_text: str
    source_ref: str = ""
    pii_level: PiiLevel = "none"
    retention_until: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class MemoryUpsertResponse(BaseModel):
    memory_id: str
    version_no: int
    scope: MemoryScope
    subject_id: str
    key: str
    created_at: str
    storage_backend: Literal["sqlite", "postgres"] = "sqlite"


class RagRetrieveRequest(BaseModel):
    run_id: str | None = None
    tenant_id: str
    query: str
    top_k: int = 5
    scopes: list[MemoryScope] = Field(default_factory=lambda: ["org", "user", "session"])
    environment: str | None = None
    object_type: str | None = None
    object_id: str | None = None


class RagHit(BaseModel):
    ref_id: str
    source_type: str
    title: str
    summary: str
    score: float
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagRetrieveResponse(BaseModel):
    query: str
    hits: list[RagHit] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
    reason: str = ""
