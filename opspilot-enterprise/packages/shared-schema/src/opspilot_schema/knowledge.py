from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class KnowledgeArticle(BaseModel):
    id: str
    title: str
    content_summary: str
    source: str
    status: str
    tags: list[str] = []
    categories: list[str] = []
    author: str
    version: str
    hit_count: int = 0
    confidence_score: float
    created_at: str
    updated_at: str
    related_incident_ids: list[str] = []


class KnowledgeImportJob(BaseModel):
    id: str
    source_type: str
    source_url: Optional[str] = None
    status: str
    articles_imported: int = 0
    articles_failed: int = 0
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
