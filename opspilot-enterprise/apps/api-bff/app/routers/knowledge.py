"""BFF router: Knowledge management proxy."""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Request

from opspilot_schema.envelope import make_error, make_success

router = APIRouter(tags=["knowledge"])

KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8072").rstrip("/")

_FALLBACK_ARTICLES = [
    {
        "id": "KB-001",
        "title": "Java Full GC storm on VMware VM",
        "content_summary": "Runbook for diagnosing JVM Full GC storms that surface as high VM CPU.",
        "source": "runbook",
        "status": "published",
        "tags": ["java", "jvm", "cpu", "vmware"],
        "categories": ["performance", "vmware"],
        "author": "ops-team",
        "version": "1.2.0",
        "hit_count": 23,
        "confidence_score": 0.92,
        "created_at": "2026-01-10T09:00:00Z",
        "updated_at": "2026-03-20T14:30:00Z",
        "related_incident_ids": ["INC-20260405-001"],
    },
]

_FALLBACK_IMPORT_JOBS = [
    {
        "id": "KIJ-FALLBACK-001",
        "source_type": "seed",
        "source_url": "vmware-golden-alerts",
        "status": "completed",
        "articles_imported": 30,
        "articles_failed": 0,
        "started_at": "2026-04-30T00:00:00Z",
        "completed_at": "2026-04-30T00:00:00Z",
        "error": None,
    }
]


async def _proxy(method: str, path: str, *, params: dict[str, Any] | None = None, json_body: Any = None, timeout: float = 60.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, f"{KNOWLEDGE_SERVICE_URL}{path}", params=params, json=json_body)
    return resp.json()


@router.get("/knowledge/articles")
async def list_articles(status: str | None = None, source: str | None = None, q: str | None = None, domain: str | None = None, environment: str | None = None) -> dict:
    try:
        return await _proxy(
            "GET",
            "/knowledge/articles",
            params={"status": status, "source": source, "q": q, "domain": domain, "environment": environment},
        )
    except httpx.HTTPError:
        data = _FALLBACK_ARTICLES
        if status:
            data = [a for a in data if a["status"] == status]
        if source:
            data = [a for a in data if a["source"] == source]
        return make_success({"items": data, "total": len(data)})


@router.get("/knowledge/articles/{article_id}")
async def get_article(article_id: str) -> dict:
    try:
        return await _proxy("GET", f"/knowledge/articles/{article_id}")
    except httpx.HTTPError:
        item = next((a for a in _FALLBACK_ARTICLES if a["id"] == article_id), None)
        if item:
            return make_success(item)
        return make_error("Article not found")


@router.get("/knowledge/import-jobs")
async def list_import_jobs() -> dict:
    try:
        return await _proxy("GET", "/knowledge/import-jobs")
    except httpx.HTTPError:
        return make_success({"items": _FALLBACK_IMPORT_JOBS, "total": len(_FALLBACK_IMPORT_JOBS)})


@router.get("/knowledge/import-jobs/{job_id}")
async def get_import_job(job_id: str) -> dict:
    try:
        return await _proxy("GET", f"/knowledge/import-jobs/{job_id}")
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.get("/knowledge/stats")
async def knowledge_stats() -> dict:
    try:
        return await _proxy("GET", "/knowledge/stats")
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.get("/knowledge/alert-items")
async def list_alert_items(
    status: str | None = None,
    vendor: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    source_type: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    try:
        return await _proxy(
            "GET",
            "/knowledge/alert-items",
            params={
                "status": status,
                "vendor": vendor,
                "category": category,
                "severity": severity,
                "tag": tag,
                "source_type": source_type,
                "q": q,
                "page": page,
                "page_size": page_size,
            },
        )
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.get("/knowledge/alert-items/{item_id}")
async def get_alert_item(item_id: str) -> dict:
    try:
        return await _proxy("GET", f"/knowledge/alert-items/{item_id}")
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/alert-items")
async def upsert_alert_item(request: Request, upsert: bool = True) -> dict:
    try:
        return await _proxy("POST", "/knowledge/alert-items", params={"upsert": upsert}, json_body=await request.json())
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/alert-items/{item_id}:deprecate")
@router.post("/knowledge/alert-items/{item_id}/deprecate")
async def deprecate_alert_item(item_id: str) -> dict:
    try:
        return await _proxy("POST", f"/knowledge/alert-items/{item_id}/deprecate")
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/alert-items:bulk-import")
async def bulk_import_alert_items(request: Request) -> dict:
    try:
        return await _proxy("POST", "/knowledge/alert-items:bulk-import", json_body=await request.json(), timeout=120.0)
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/import/validate")
async def validate_import(request: Request) -> dict:
    try:
        return await _proxy("POST", "/knowledge/import/validate", json_body=await request.json(), timeout=120.0)
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/alert-match")
async def alert_match(request: Request) -> dict:
    try:
        return await _proxy("POST", "/knowledge/alert-match", json_body=await request.json())
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/feedback")
async def create_feedback(request: Request) -> dict:
    try:
        return await _proxy("POST", "/knowledge/feedback", json_body=await request.json())
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")


@router.post("/knowledge/importers/prometheus-rules")
async def import_prometheus_rules(request: Request) -> dict:
    try:
        return await _proxy("POST", "/knowledge/importers/prometheus-rules", json_body=await request.json(), timeout=120.0)
    except httpx.HTTPError as exc:
        return make_error(f"Knowledge service unreachable: {exc}")
