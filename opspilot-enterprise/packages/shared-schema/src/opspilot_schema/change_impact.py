from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class ChangeImpactRequest(BaseModel):
    change_type: str
    target_type: str
    target_id: str
    requested_action: str
    environment: str
    change_window: str | None = None


class ImpactedObject(BaseModel):
    object_type: str
    object_id: str
    object_name: str
    impact_type: str
    severity: str


class DependencyNode(BaseModel):
    id: str
    name: str
    type: str
    children: list[DependencyNode] = []


class ChangeImpactResult(BaseModel):
    analysis_id: str
    target: dict
    action: str
    risk_score: int
    risk_level: Literal["critical", "high", "medium", "low"]
    impacted_objects: list[ImpactedObject] = []
    checks_required: list[str] = []
    rollback_plan: list[str] = []
    approval_suggestion: Literal["required", "recommended", "not_required"]
    dependency_graph: list[DependencyNode] = []
