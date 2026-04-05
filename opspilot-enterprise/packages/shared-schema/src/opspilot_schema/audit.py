from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


class AuditLog(BaseModel):
    id: str
    event_type: str
    severity: str
    actor: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    resource_name: str
    outcome: str
    reason: Optional[str] = None
    incident_ref: Optional[str] = None
    request_id: str
    trace_id: str
    timestamp: str
    metadata: dict[str, Any] = {}
