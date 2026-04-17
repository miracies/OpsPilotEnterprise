from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .intent import IntentDomain, RiskLevel

InteractionKind = Literal["clarify", "approve"]
ClarifyReasonCode = Literal[
    "ambiguous_intent",
    "missing_slot",
    "conflicting_resource",
    "unsafe_default",
]
InteractionStatus = Literal["pending", "answered", "approved", "rejected", "expired"]
ApprovalScope = Literal["once", "session"]
ApprovalDecisionOutcome = Literal["approved", "rejected", "expired"]


class ClarifyChoice(BaseModel):
    id: str
    label: str


class ClarifyRequest(BaseModel):
    interaction_id: str
    run_id: str
    question: str
    choices: list[str] = Field(default_factory=list, max_length=4)
    allow_free_text: bool = True
    reason_code: ClarifyReasonCode = "ambiguous_intent"
    expires_at: str
    created_at: str
    created_by: str = "system"


class ClarifyResponse(BaseModel):
    interaction_id: str
    selected_choice: Optional[str] = None
    free_text: Optional[str] = None
    submitted_at: str
    responded_by: str = "user"


class ClarifyCreateRequest(BaseModel):
    run_id: str
    question: str
    choices: list[str] = Field(default_factory=list, max_length=4)
    allow_free_text: bool = True
    reason_code: ClarifyReasonCode = "ambiguous_intent"
    expires_in_seconds: int = 900


class ClarifyRecord(ClarifyRequest):
    status: InteractionStatus = "pending"
    selected_choice: Optional[str] = None
    free_text: Optional[str] = None
    responded_at: Optional[str] = None
    responded_by: Optional[str] = None


class ClarifyAnswerRequest(BaseModel):
    selected_choice: Optional[str] = None
    free_text: Optional[str] = None
    responded_by: str = "user"


class ResourceRef(BaseModel):
    type: str
    id: str
    name: str = ""


class ResourceScope(BaseModel):
    environment: str = "unknown"
    resources: list[ResourceRef] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approval_id: str
    run_id: str
    summary: str
    domain: IntentDomain
    action: str
    risk_level: RiskLevel
    resource_scope: ResourceScope
    command_preview: list[str] = Field(default_factory=list)
    plan_steps: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    allowed_scopes: list[ApprovalScope] = Field(default_factory=lambda: ["once"])
    expires_at: str
    created_at: str
    created_by: str = "system"


class ApprovalResponse(BaseModel):
    approval_id: str
    status: InteractionStatus = "pending"
    decision: Optional[ApprovalDecisionOutcome] = None
    final_scope: Optional[ApprovalScope] = None
    comment: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    next_action: Optional[str] = None


class ApprovalCreateRequest(BaseModel):
    run_id: str
    summary: str
    domain: IntentDomain
    action: str
    risk_level: RiskLevel
    resource_scope: ResourceScope
    command_preview: list[str] = Field(default_factory=list)
    plan_steps: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    allowed_scopes: list[ApprovalScope] = Field(default_factory=lambda: ["once"])
    expires_in_seconds: int = 900


class ApprovalRecord(ApprovalRequest):
    status: InteractionStatus = "pending"
    decision: Optional[ApprovalDecisionOutcome] = None
    final_scope: Optional[ApprovalScope] = None
    comment: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class ApprovalDecision(BaseModel):
    decision: ApprovalDecisionOutcome
    scope: Optional[ApprovalScope] = None
    comment: Optional[str] = None
    approved_by: str = "user"
    approved_at: str


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecisionOutcome
    scope: Optional[ApprovalScope] = None
    comment: Optional[str] = None
    approved_by: str = "user"


class InteractionEnvelope(BaseModel):
    kind: InteractionKind
    clarify: Optional[ClarifyRecord] = None
    approval: Optional[ApprovalRecord] = None
    next_action: Optional[str] = None
