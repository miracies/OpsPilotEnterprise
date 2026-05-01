"""BFF router: Case archive (proxy to event-ingestion-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["cases"])

EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")

_FALLBACK_CASES = [
    {
        "id": "CASE-20260320",
        "title": "VM CPU pressure caused by Java GC storm",
        "summary": "High VM CPU and high JVM GC pause time on a production VM.",
        "category": "performance",
        "status": "archived",
        "severity": "high",
        "tags": ["vmware", "cpu", "jvm"],
        "incident_refs": ["INC-20260320-001"],
        "root_cause_summary": "Application GC storm saturated VM CPU.",
        "resolution_summary": "Tuned JVM heap and moved noisy VM away from a hot host.",
        "lessons_learned": "Check guest process CPU before host capacity changes.",
        "author": "system",
        "created_at": "2026-03-20T08:00:00Z",
        "archived_at": "2026-03-21T09:00:00Z",
        "similarity_score": 0.82,
        "hit_count": 3,
        "knowledge_refs": ["AK-VMWARE-01-001"],
    },
    {
        "id": "CASE-20260315",
        "title": "Datastore snapshot chain caused capacity alarm",
        "summary": "Backup failure left a long snapshot chain and triggered datastore usage alarm.",
        "category": "capacity",
        "status": "archived",
        "severity": "medium",
        "tags": ["vmware", "snapshot", "datastore"],
        "incident_refs": ["INC-20260315-001"],
        "root_cause_summary": "Backup job left a long snapshot chain.",
        "resolution_summary": "Consolidated snapshots after free-space verification.",
        "lessons_learned": "Pair datastore alarms with backup job status.",
        "author": "system",
        "created_at": "2026-03-15T08:00:00Z",
        "archived_at": "2026-03-16T10:00:00Z",
        "similarity_score": 0.91,
        "hit_count": 5,
        "knowledge_refs": ["AK-VMWARE-04-017"],
    },
]


@router.get("/cases")
async def list_cases(category: str | None = None, status: str | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            params = {"category": category, "status": status}
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/cases", params=params)
            payload = resp.json()
            if payload.get("success"):
                return payload
        except httpx.HTTPError as exc:
            pass
    data = _FALLBACK_CASES
    if category:
        data = [case for case in data if case["category"] == category]
    if status:
        data = [case for case in data if case["status"] == status]
    from opspilot_schema.envelope import make_success

    return make_success({"items": data, "total": len(data)})


@router.post("/cases/similar")
async def similar_cases(body: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/cases/similar", json=body)
            payload = resp.json()
            if payload.get("success"):
                return payload
        except httpx.HTTPError as exc:
            pass
    query = " ".join(str(body.get(key) or "") for key in ("title", "summary", "category", "root_cause_summary")).lower()
    tags = set(body.get("tags") or [])
    scored = []
    for case in _FALLBACK_CASES:
        blob = " ".join([case["title"], case["summary"], case["category"], " ".join(case["tags"])]).lower()
        score = sum(1 for term in query.split() if term and term in blob) / max(len(query.split()), 1)
        if tags & set(case["tags"]):
            score += 0.2
        item = dict(case)
        item["similarity_score"] = round(min(score, 0.99), 3)
        item["matched_fields"] = [
            field
            for field in ("title", "summary", "category", "tags", "knowledge_refs")
            if field == "tags" and tags & set(case.get("tags") or [])
            or field != "tags" and str(body.get(field) or "").lower() in blob
        ]
        if item["similarity_score"] > 0:
            scored.append(item)
    scored.sort(key=lambda item: item["similarity_score"], reverse=True)
    from opspilot_schema.envelope import make_success

    return make_success({"items": scored[: body.get("limit", 5)], "total": len(scored[: body.get("limit", 5)])})


@router.post("/cases/from-incident")
async def case_from_incident(request: Request):
    body = await request.json()
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{EVENT_INGESTION_URL}/api/v1/cases/from-incident", json=body)
            payload = resp.json()
            if payload.get("success"):
                return payload
            return payload
        except httpx.HTTPError as exc:
            return make_error(f"event ingestion unreachable: {exc}")


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/cases/{case_id}")
            payload = resp.json()
            if payload.get("success"):
                return payload
        except httpx.HTTPError as exc:
            pass
    from opspilot_schema.envelope import make_success

    item = next((case for case in _FALLBACK_CASES if case["id"] == case_id), None)
    if item:
        return make_success(item)
    return make_error(f"case not found: {case_id}")
