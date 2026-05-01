from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


class OpsPolicy(BaseModel):
    id: str
    name: str
    description: str
    type: str
    status: str
    effect: str
    scope: list[str] = []
    conditions: dict[str, Any] = {}
    created_at: str
    updated_at: str
    hit_count: int = 0
    last_hit_at: Optional[str] = None
    author: str
    version: str
    rego_snippet: Optional[str] = None


class PolicyHitRecord(BaseModel):
    id: str
    policy_id: str
    policy_name: str
    effect: str
    actor: str
    tool_name: str
    resource: str
    outcome: str
    timestamp: str
    trace_id: str
