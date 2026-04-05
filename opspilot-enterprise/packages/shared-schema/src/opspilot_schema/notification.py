from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: str
    title: str
    content: str
    priority: str
    status: str
    incident_ref: Optional[str] = None
    channels: list[str] = []
    recipients: list[str] = []
    created_at: str
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    escalation_count: int = 0
    next_escalation_at: Optional[str] = None


class OnCallShift(BaseModel):
    id: str
    name: str
    team: str
    members: list[str]
    start_at: str
    end_at: str
    active: bool
