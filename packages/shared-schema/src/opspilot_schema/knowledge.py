from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class KnowledgeCitation(BaseModel):
    article_id: str
    title: str
    relevance_score: float
    why_selected: str


class KnowledgeArticle(BaseModel):
    id: str
    title: str
    content_summary: str
    source: str
    status: str
    tags: list[str] = []
    categories: list[str] = []
    author: str
    version: str
    hit_count: int = 0
    confidence_score: float
    relevance_score: float | None = None
    why_selected: str | None = None
    citations: list[KnowledgeCitation] = []
    created_at: str
    updated_at: str
    related_incident_ids: list[str] = []


class KnowledgeImportJob(BaseModel):
    id: str
    source_type: str
    source_url: Optional[str] = None
    status: str
    articles_imported: int = 0
    articles_failed: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    total: int = 0
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class DecisionRule(BaseModel):
    condition: str
    conclusion: str
    confidence_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    required_evidence: list[str] = Field(default_factory=list)


AlertKnowledgeCategory = Literal[
    "resource",
    "ha_cluster",
    "vmotion_drs",
    "storage",
    "network",
    "vm_level",
    "other",
]
AlertKnowledgeSeverity = Literal["info", "warning", "critical"]
AlertKnowledgeStatus = Literal["draft", "published", "deprecated"]


class AlertKnowledgeAutomation(BaseModel):
    safe_actions: list[str] = Field(default_factory=list)
    approval_actions: list[str] = Field(default_factory=list)
    suppression_window: str | None = None

    @field_validator("safe_actions")
    @classmethod
    def safe_actions_must_be_read_only(cls, values: list[str]) -> list[str]:
        risky_tokens = (
            "migrate",
            "restart",
            "reboot",
            "power_off",
            "poweroff",
            "delete",
            "remove",
            "consolidate",
            "balance",
        )
        bad = [item for item in values if any(token in item.lower() for token in risky_tokens)]
        if bad:
            raise ValueError(f"safe_actions cannot contain approval-required actions: {bad}")
        return values


class AlertKnowledgeSource(BaseModel):
    type: Literal["manual", "rule", "kb", "case", "external", "seed"] = "manual"
    title: str
    url: str | None = None
    trust_score: float = Field(default=0.8, ge=0.0, le=1.0)


class AlertKnowledge(BaseModel):
    id: str
    alert_name: str
    vendor: str = "vmware"
    domain: str = "virtualization"
    category: AlertKnowledgeCategory
    severity: AlertKnowledgeSeverity
    aliases: list[str] = Field(default_factory=list)
    symptoms: list[str]
    possible_causes: list[str]
    diagnostic_steps: list[str]
    decision_tree: list[DecisionRule]
    evidence_required: list[str]
    evidence_optional: list[str] = Field(default_factory=list)
    remediation: list[str]
    automation: AlertKnowledgeAutomation
    source: AlertKnowledgeSource
    status: AlertKnowledgeStatus = "published"
    version: str = "1.0.0"
    trust_score: float = 0.8
    hit_count: int = 0
    case_refs: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    match_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    owner: str | None = None
    reviewer: str | None = None
    review_notes: str | None = None
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_decision_tree(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        tree = data.get("decision_tree")
        if isinstance(tree, list):
            normalized = []
            for item in tree:
                if isinstance(item, str):
                    normalized.append(
                        {
                            "condition": item,
                            "conclusion": item,
                            "confidence_delta": 0.0,
                            "required_evidence": [],
                        }
                    )
                else:
                    normalized.append(item)
            data = dict(data)
            data["decision_tree"] = normalized
        return data

    @field_validator(
        "symptoms",
        "possible_causes",
        "diagnostic_steps",
        "decision_tree",
        "evidence_required",
        "remediation",
    )
    @classmethod
    def non_empty_lists(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("must contain at least one item")
        return values

    @model_validator(mode="after")
    def normalize_trust_score(self) -> "AlertKnowledge":
        self.trust_score = max(0.0, min(float(self.trust_score), 1.0))
        return self


class AlertKnowledgeBulkImportBody(BaseModel):
    items: list[AlertKnowledge]
    source_type: str = "manual"
    upsert: bool = True
    dry_run: bool = False
    source_url: str | None = None


class KnowledgeImportValidateBody(BaseModel):
    content: str
    source_type: str = "manual"
    content_type: Literal["json", "jsonl", "prometheus_rules"] = "jsonl"
    publish: bool = False
    upsert: bool = True


class AlertMatchRequest(BaseModel):
    alert_name: str | None = None
    summary: str | None = None
    description: str | None = None
    vendor: str | None = None
    domain: str | None = None
    category: str | None = None
    severity: str | None = None
    labels: dict[str, Any] = Field(default_factory=dict)
    evidence_present: list[str] = Field(default_factory=list)
    top_k: int = 5


class AlertKnowledgeMatch(BaseModel):
    item: AlertKnowledge
    relevance_score: float
    why_selected: str
    matched_fields: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    missing_critical_evidence: list[str] = Field(default_factory=list)


class AlertMatchResponse(BaseModel):
    matches: list[AlertKnowledgeMatch]
    missing_evidence: list[str] = Field(default_factory=list)
    required_evidence_types: list[str] = Field(default_factory=list)
    diagnostic_steps: list[str] = Field(default_factory=list)
    safe_actions: list[str] = Field(default_factory=list)
    approval_actions: list[str] = Field(default_factory=list)
    missing_critical_evidence: list[str] = Field(default_factory=list)
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    why_selected: str = ""


class KnowledgeFeedbackBody(BaseModel):
    alert_knowledge_id: str | None = None
    incident_id: str | None = None
    match_correct: bool
    actual_root_cause: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    accepted_actions: list[str] = Field(default_factory=list)
    comment: str | None = None
    user_id: str = "ops-user"
