from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class CaseArchive(BaseModel):
    id: str
    title: str
    summary: str
    category: str
    status: str
    severity: str
    tags: list[str] = []
    incident_refs: list[str] = []
    root_cause_summary: str
    resolution_summary: str
    lessons_learned: str
    author: str
    created_at: str
    archived_at: Optional[str] = None
    similarity_score: Optional[float] = None
    hit_count: int = 0
    knowledge_refs: list[str] = []
