from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

IntentDomain = Literal["vmware", "k8s", "host", "jenkins", "knowledge", "unknown"]
RecoveryDecision = Literal["recovered", "clarify_required", "rejected"]
RiskLevel = Literal["L0", "L1", "L2", "L3", "L4"]
SlotSource = Literal["user", "memory", "cmdb", "tool_discovery", "inferred"]
EvidenceSourceType = Literal["session", "knowledge", "cmdb", "tool_discovery"]


class SlotValue(BaseModel):
    name: str
    value: Any = None
    source: SlotSource = "user"
    confidence: float = 0.0


class EvidenceRef(BaseModel):
    type: EvidenceSourceType
    ref_id: str
    summary: str = ""
    score: float = 0.0


class ScoreBreakdown(BaseModel):
    rules: float = 0.0
    entity_match: float = 0.0
    slot_completeness: float = 0.0
    memory_boost: float = 0.0
    llm_rerank: float = 0.0


class IntentCandidate(BaseModel):
    intent_code: str
    domain: IntentDomain
    action: str
    description: str = ""
    resource_scope: Literal["single", "multiple", "cluster", "global"] = "single"
    environment: Optional[str] = None
    memory_refs: list[str] = Field(default_factory=list)
    score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    slots: list[SlotValue] = Field(default_factory=list)
    missing_slots: list[str] = Field(default_factory=list)
    inferred_environment: Optional[str] = None
    inferred_risk_level: Optional[RiskLevel] = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class IntentRecoveryRun(BaseModel):
    run_id: str
    conversation_id: str
    user_id: str
    channel: str = "web"
    tenant_id: Optional[str] = None
    raw_utterance: str
    normalized_utterance: str
    candidates: list[IntentCandidate] = Field(default_factory=list)
    chosen_intent: Optional[IntentCandidate] = None
    decision: RecoveryDecision = "clarify_required"
    clarify_reasons: list[str] = Field(default_factory=list)
    rejected_reasons: list[str] = Field(default_factory=list)
    created_at: str

    @property
    def top_candidates(self) -> list[IntentCandidate]:
        return self.candidates[:3]

    @property
    def missing_slots(self) -> list[str]:
        if self.chosen_intent:
            return self.chosen_intent.missing_slots
        if self.candidates:
            return self.candidates[0].missing_slots
        return []

    @property
    def evidence_summary(self) -> list[str]:
        evidence = self.chosen_intent.evidence if self.chosen_intent else (self.candidates[0].evidence if self.candidates else [])
        return [item.summary for item in evidence if item.summary]


class IntentRecoverInput(BaseModel):
    conversation_id: str
    user_id: str
    channel: str = "web"
    utterance: str
    tenant_id: Optional[str] = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    memory: list[str] = Field(default_factory=list)
    resource_catalog: list[dict[str, Any]] = Field(default_factory=list)
