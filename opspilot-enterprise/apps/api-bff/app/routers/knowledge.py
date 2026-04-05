"""BFF router: Knowledge management."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["knowledge"])

_ARTICLES = [
    {"id": "KB-001", "title": "Java Full GC 风暴导致 vCPU 高占用的诊断方法", "content_summary": "当 VMware 虚拟机内 Java 应用发生 Full GC 风暴时，会导致宿主机 CPU 利用率骤升。本文介绍诊断步骤：检查 GC 日志、调整堆内存、设置 GC 策略。", "source": "runbook", "status": "published", "tags": ["java", "jvm", "cpu", "gc"], "categories": ["性能", "JVM"], "author": "ops-team", "version": "1.2.0", "hit_count": 23, "confidence_score": 0.92, "created_at": "2026-01-10T09:00:00Z", "updated_at": "2026-03-20T14:30:00Z", "related_incident_ids": ["INC-20260405-001"]},
    {"id": "KB-002", "title": "VMware HA 隔离事件处理流程", "content_summary": "当主机检测到网络隔离时，HA 会按隔离响应策略处理 VM。本文包含隔离响应策略配置、排查步骤和最佳实践。", "source": "runbook", "status": "published", "tags": ["vmware", "ha", "network"], "categories": ["高可用", "VMware"], "author": "ops-team", "version": "2.0.1", "hit_count": 15, "confidence_score": 0.88, "created_at": "2025-11-05T10:00:00Z", "updated_at": "2026-02-14T11:00:00Z", "related_incident_ids": ["INC-20260404-005"]},
    {"id": "KB-003", "title": "NFS 数据存储快照容量管理最佳实践", "content_summary": "快照占用大量存储空间是生产环境常见问题。本文介绍快照保留策略、自动化清理配置和容量规划建议。", "source": "confluence", "status": "published", "tags": ["vmware", "nfs", "snapshot", "capacity"], "categories": ["容量", "存储"], "author": "storage-team", "version": "1.0.3", "hit_count": 31, "confidence_score": 0.95, "created_at": "2025-08-20T08:00:00Z", "updated_at": "2026-01-08T16:00:00Z", "related_incident_ids": ["INC-20260405-002"]},
    {"id": "KB-004", "title": "AI 根因分析结果可解释性指南", "content_summary": "OpsPilot RCA 模块输出的根因候选置信度计算方式、证据权重说明和人工复核建议。", "source": "ai_generated", "status": "reviewing", "tags": ["aiops", "rca"], "categories": ["AI", "诊断"], "author": "ai-team", "version": "0.9.0", "hit_count": 7, "confidence_score": 0.71, "created_at": "2026-03-01T12:00:00Z", "updated_at": "2026-04-01T09:00:00Z", "related_incident_ids": []},
]

_IMPORT_JOBS = [
    {"id": "KIJ-001", "source_type": "confluence", "source_url": "https://confluence.corp.local/space/OPS", "status": "completed", "articles_imported": 48, "articles_failed": 2, "started_at": "2026-04-04T02:00:00Z", "completed_at": "2026-04-04T02:18:00Z", "error": None},
    {"id": "KIJ-002", "source_type": "runbook", "source_url": "https://gitlab.corp.local/runbooks", "status": "running", "articles_imported": 12, "articles_failed": 0, "started_at": "2026-04-05T09:00:00Z", "completed_at": None, "error": None},
]


@router.get("/knowledge/articles")
async def list_articles(status: str | None = None, source: str | None = None):
    data = _ARTICLES
    if status:
        data = [a for a in data if a["status"] == status]
    if source:
        data = [a for a in data if a["source"] == source]
    return make_success({"items": data, "total": len(data)})


@router.get("/knowledge/articles/{article_id}")
async def get_article(article_id: str):
    item = next((a for a in _ARTICLES if a["id"] == article_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Article not found")
    return make_success(item)


@router.get("/knowledge/import-jobs")
async def list_import_jobs():
    return make_success({"items": _IMPORT_JOBS})
