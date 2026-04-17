"""Risk Strategy Engine rule schemas.

Corresponds to OpsPilot Codex 开发说明书 §风险策略引擎.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .intent import IntentDomain, RiskLevel
from .interaction import ApprovalScope

EnvironmentName = Literal["dev", "test", "staging", "prod"]
ResourceScopeName = Literal["single", "multiple", "cluster", "global"]


class RiskPolicyMatcher(BaseModel):
    domain: list[IntentDomain] = Field(default_factory=list)
    action: list[str] = Field(default_factory=list)
    environment: list[EnvironmentName] = Field(default_factory=list)
    resource_scope: list[ResourceScopeName] = Field(default_factory=list)
    tool: list[str] = Field(default_factory=list)
    command_regex: list[str] = Field(default_factory=list)


class RiskPolicyDecision(BaseModel):
    risk_level: RiskLevel = "L0"
    require_clarify: bool = False
    require_approval: bool = False
    allow_scopes: list[ApprovalScope] = Field(default_factory=lambda: ["once"])
    deny: bool = False
    require_rollback_plan: bool = False
    require_change_ticket: bool = False


class RiskPolicyRule(BaseModel):
    rule_code: str
    enabled: bool = True
    priority: int = 100
    matcher: RiskPolicyMatcher = Field(default_factory=RiskPolicyMatcher)
    decision: RiskPolicyDecision = Field(default_factory=RiskPolicyDecision)
    remark: Optional[str] = None
    updated_at: Optional[str] = None


class RiskEvaluationInput(BaseModel):
    domain: IntentDomain
    action: str
    environment: EnvironmentName = "prod"
    resource_scope: ResourceScopeName = "single"
    tool: Optional[str] = None
    command_preview: list[str] = Field(default_factory=list)


class RiskEvaluationResult(BaseModel):
    risk_level: RiskLevel
    require_clarify: bool = False
    require_approval: bool = False
    allowed_scopes: list[ApprovalScope] = Field(default_factory=lambda: ["once"])
    deny: bool = False
    require_rollback_plan: bool = False
    require_change_ticket: bool = False
    matched_rule_code: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
