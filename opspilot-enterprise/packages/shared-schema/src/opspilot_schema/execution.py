from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionStatus = Literal[
    "draft",
    "dry_run_ready",
    "pending_approval",
    "executing",
    "success",
    "failed",
    "canceled",
]


class ExecutionTarget(BaseModel):
    object_id: str
    object_name: str
    object_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionDryRunTargetResult(BaseModel):
    object_id: str
    object_name: str
    status: Literal["ok", "error"]
    message: str
    preview: dict[str, Any] = Field(default_factory=dict)


class ExecutionPolicyResult(BaseModel):
    allowed: bool
    require_approval: bool
    reason: str
    matched_policies: list[str] = Field(default_factory=list)
    source: str | None = None


class ExecutionDryRunResult(BaseModel):
    can_submit: bool
    require_approval: bool
    policy: ExecutionPolicyResult
    action_type: str
    risk_level: str
    risk_score: int
    capability: Literal["single", "batch"]
    target_results: list[ExecutionDryRunTargetResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionRequest(BaseModel):
    id: str
    tool_name: str
    action_type: str
    environment: str
    requester: str
    status: ExecutionStatus
    incident_id: str | None = None
    change_analysis_ref: str | None = None
    approval_id: str | None = None
    targets: list[ExecutionTarget] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run_result: ExecutionDryRunResult | None = None
    result: dict[str, Any] | None = None
    created_at: str
    updated_at: str
