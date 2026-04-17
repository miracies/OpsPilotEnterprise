"""OpsPilot Knowledge Service - knowledge articles, KB search, case archive."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opspilot_schema.envelope import make_success

app = FastAPI(title="OpsPilot Knowledge Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ARTICLES = [
    {
        "id": "KB-001",
        "title": "Java Full GC 风暴导致 vCPU 高占用的诊断方法",
        "content_summary": "针对虚拟化环境下 JVM Full GC 风暴引发 CPU 飙升的排查流程与缓解动作。",
        "source": "runbook",
        "status": "published",
        "tags": ["java", "jvm", "cpu", "vmware"],
        "author": "ops-team",
        "version": "1.2.0",
        "hit_count": 23,
        "confidence_score": 0.92,
        "created_at": "2026-01-10T09:00:00Z",
        "updated_at": "2026-03-20T14:30:00Z",
    },
    {
        "id": "KB-002",
        "title": "VMware HA 隔离事件处理流程",
        "content_summary": "处理 ESXi 主机网络隔离与 HA 触发的分级处置手册。",
        "source": "runbook",
        "status": "published",
        "tags": ["vmware", "ha", "network", "host"],
        "author": "ops-team",
        "version": "2.0.1",
        "hit_count": 15,
        "confidence_score": 0.88,
        "created_at": "2025-11-05T10:00:00Z",
        "updated_at": "2026-02-14T11:00:00Z",
    },
    {
        "id": "KB-003",
        "title": "NFS 数据存储快照容量管理最佳实践",
        "content_summary": "快照堆积、容量告警、存储性能抖动场景下的治理建议。",
        "source": "confluence",
        "status": "published",
        "tags": ["vmware", "nfs", "snapshot", "datastore"],
        "author": "storage-team",
        "version": "1.0.3",
        "hit_count": 31,
        "confidence_score": 0.95,
        "created_at": "2025-08-20T08:00:00Z",
        "updated_at": "2026-01-08T16:00:00Z",
    },
]

_CASES = [
    {"id": "CASE-20260320", "title": "Java GC 风暴导致主机 CPU 飙升", "category": "performance", "status": "archived", "severity": "high", "tags": ["jvm", "cpu"], "similarity_score": 0.82, "hit_count": 3, "archived_at": "2026-03-21T09:00:00Z"},
    {"id": "CASE-20260315", "title": "NFS 存储快照堆积导致容量告警", "category": "capacity", "status": "archived", "severity": "medium", "tags": ["nfs", "snapshot"], "similarity_score": 0.91, "hit_count": 5, "archived_at": "2026-03-16T10:00:00Z"},
]


@app.get("/health")
async def health():
    return make_success({"status": "ok", "service": "knowledge-service"})


def _score_article(item: dict, q: str | None, domain: str | None, environment: str | None) -> tuple[float, str]:
    score = float(item.get("confidence_score") or 0.5)
    reasons: list[str] = []
    blob = f"{item.get('title', '')} {item.get('content_summary', '')} {' '.join(item.get('tags', []))}".lower()
    if q:
        terms = [x for x in re.split(r"[\s,，;；]+", q.lower()) if x]
        matched = sum(1 for t in terms if t in blob)
        if matched:
            score += 0.07 * matched
            reasons.append(f"命中查询词 {matched} 个")
    if domain and domain.lower() in blob:
        score += 0.08
        reasons.append(f"匹配域 {domain}")
    if environment and environment.lower() in {"prod", "production", "生产"} and ("runbook" in str(item.get("source"))):
        score += 0.03
        reasons.append("生产场景优先 runbook")
    return min(score, 0.99), "；".join(reasons) or "基础相关性"


@app.get("/knowledge/articles")
async def list_articles(status: Optional[str] = None, q: Optional[str] = None, domain: Optional[str] = None, environment: Optional[str] = None):
    data = _ARTICLES
    if status:
        data = [a for a in data if a["status"] == status]
    ranked: list[dict] = []
    for item in data:
        score, why = _score_article(item, q, domain, environment)
        enriched = dict(item)
        enriched["relevance_score"] = round(score, 3)
        enriched["why_selected"] = why
        enriched["citations"] = [
            {
                "article_id": item["id"],
                "title": item["title"],
                "relevance_score": round(score, 3),
                "why_selected": why,
            }
        ]
        ranked.append(enriched)
    ranked.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return make_success({"items": ranked, "total": len(ranked)})


@app.get("/knowledge/articles/{article_id}")
async def get_article(article_id: str):
    item = next((a for a in _ARTICLES if a["id"] == article_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Article not found")
    return make_success(item)


@app.get("/cases")
async def list_cases(category: Optional[str] = None):
    data = _CASES if not category else [c for c in _CASES if c["category"] == category]
    return make_success({"items": data, "total": len(data)})


@app.get("/cases/{case_id}")
async def get_case(case_id: str):
    item = next((c for c in _CASES if c["id"] == case_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Case not found")
    return make_success(item)
