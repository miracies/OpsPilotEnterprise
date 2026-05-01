from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MemoryType = Literal[
    "user_memory",
    "resource_memory",
    "incident_memory",
    "vmware_incident_memory",
    "change_memory",
    "knowledge_memory",
]
MemoryImportance = Literal["low", "medium", "high", "critical"]
MemoryRetentionPolicy = Literal["short_term", "medium_term", "long_term", "permanent"]
MemoryStatus = Literal["active", "archived", "deleted", "invalid", "expired", "downgraded", "duplicate"]
MemoryMergeStrategy = Literal["append_evidence", "replace_summary", "mark_duplicate"]


class MemoryEntity(BaseModel):
    id: str | None = None
    entity_type: str
    entity_id: str | None = None
    entity_name: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class MemoryEvidenceRef(BaseModel):
    id: str | None = None
    evidence_id: str
    evidence_type: str | None = None
    evidence_uri: str | None = None


class MemoryRelation(BaseModel):
    id: str | None = None
    source_memory_id: str
    relation_type: str
    target_type: str
    target_id: str
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class MemoryItem(BaseModel):
    id: str
    tenant_id: str
    user_id: str | None = None
    memory_type: str
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    source: str
    source_id: str | None = None
    importance: MemoryImportance = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    retention_policy: MemoryRetentionPolicy = "long_term"
    status: MemoryStatus = "active"
    created_at: str
    updated_at: str
    expire_at: str | None = None
    entities: list[MemoryEntity] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[MemoryEvidenceRef] = Field(default_factory=list)
    relations: list[MemoryRelation] = Field(default_factory=list)
    score: float | None = None
    graph_sync_status: str | None = None


class MemoryCreateRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str | None = None
    memory_type: str
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    source: str
    source_id: str | None = None
    importance: MemoryImportance = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    retention_policy: MemoryRetentionPolicy = "long_term"
    expire_at: str | None = None
    entities: list[MemoryEntity] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    evidence_refs: list[MemoryEvidenceRef] = Field(default_factory=list)
    embedding: list[float] | None = None


class MemoryListResponse(BaseModel):
    items: list[MemoryItem] = Field(default_factory=list)
    total: int = 0


class MemorySearchFilters(BaseModel):
    memory_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None
    status: MemoryStatus | None = "active"
    source: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MemorySearchRequest(BaseModel):
    tenant_id: str = "default"
    query: str = ""
    filters: MemorySearchFilters = Field(default_factory=MemorySearchFilters)
    top_k: int = Field(default=5, ge=1, le=50)
    include_graph: bool = True


class MemorySearchHit(BaseModel):
    memory: MemoryItem
    score: float
    reasons: list[str] = Field(default_factory=list)


class MemorySearchResponse(BaseModel):
    query: str
    hits: list[MemorySearchHit] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


class MemoryMergeRequest(BaseModel):
    target_memory_id: str
    merge_reason: str
    merge_strategy: MemoryMergeStrategy = "append_evidence"


class MemoryStatusUpdateRequest(BaseModel):
    status: MemoryStatus
    reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryPolicyRule(BaseModel):
    id: str
    name: str
    enabled: bool = True
    memory_type: str | None = None
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    retention_policy: MemoryRetentionPolicy = "long_term"
    blocked_patterns: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class MemoryPolicyListResponse(BaseModel):
    items: list[MemoryPolicyRule] = Field(default_factory=list)


class MemoryAgentAnalyzeRequest(BaseModel):
    request_id: str
    tenant_id: str = "default"
    user_id: str | None = None
    session_id: str | None = None
    source: str
    input_type: str
    content: dict[str, Any] = Field(default_factory=dict)
    auto_write: bool = True


class MemoryAgentAnalyzeResponse(BaseModel):
    request_id: str
    should_write_memory: bool
    memory_type: str | None = None
    importance: MemoryImportance = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    retention_policy: MemoryRetentionPolicy = "long_term"
    memory_items: list[MemoryItem] = Field(default_factory=list)
    merge_candidates: list[MemorySearchHit] = Field(default_factory=list)
    reason: str = ""


class MemoryContextRequest(BaseModel):
    tenant_id: str = "default"
    query: str
    agent: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class MemoryContextResponse(BaseModel):
    similar_incidents: list[MemorySearchHit] = Field(default_factory=list)
    resource_history: list[MemorySearchHit] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


class SopCandidate(BaseModel):
    id: str
    tenant_id: str
    title: str
    summary: str
    source_memory_ids: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    status: Literal["candidate", "promoted", "rejected"] = "candidate"
    knowledge_article_id: str | None = None
    created_at: str
    updated_at: str


class SopCandidateCreateRequest(BaseModel):
    tenant_id: str = "default"
    title: str
    summary: str
    source_memory_ids: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)

