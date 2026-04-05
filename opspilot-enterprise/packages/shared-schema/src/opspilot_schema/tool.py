from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class ToolMeta(BaseModel):
    name: str
    display_name: str
    category: str
    domain: str
    provider: str
    action_type: Literal["read", "write", "dangerous"]
    risk_level: Literal["low", "medium", "high", "critical"]
    approval_required: bool
    timeout_seconds: int
    idempotent: bool
    version: str
    tags: list[str] = []


class ToolHealthStatus(BaseModel):
    name: str
    provider: str
    healthy: bool
    last_check: str
    latency_ms: int
