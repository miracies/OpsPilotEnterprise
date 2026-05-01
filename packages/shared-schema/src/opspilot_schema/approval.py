from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    id: str
    title: str
    description: str
    action_type: str
    risk_level: str
    risk_score: int
    status: str
    requester: str
    assignee: Optional[str] = None
    incident_ref: Optional[str] = None
    change_analysis_ref: Optional[str] = None
    target_object: str
    target_object_type: str
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None
    decision_comment: Optional[str] = None
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    tags: list[str] = []


class ApprovalDecision(BaseModel):
    request_id: str
    decision: str
    comment: str
    decided_by: str
    decided_at: str
