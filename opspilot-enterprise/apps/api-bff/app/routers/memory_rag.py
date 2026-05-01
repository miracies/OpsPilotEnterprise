from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(tags=["memory-rag"])
MEMORY_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "http://127.0.0.1:8073").rstrip("/")


async def _proxy(method: str, path: str, *, json_body: dict | list | None = None, params: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.request(method, f"{MEMORY_SERVICE_URL}{path}", json=json_body, params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Memory service unreachable: {exc}")


@router.post("/memory/upsert")
async def memory_upsert(body: dict):
    payload = {
        "tenant_id": body.get("tenant_id", "default"),
        "user_id": body.get("subject_id") if body.get("scope") == "user" else None,
        "memory_type": body.get("metadata", {}).get("memory_type", "user_memory" if body.get("scope") == "user" else "knowledge_memory"),
        "title": str(body.get("key") or "memory"),
        "summary": str(body.get("value_text") or ""),
        "content": {"legacy_memory": body},
        "source": str(body.get("source_ref") or "legacy-memory-upsert"),
        "source_id": body.get("memory_id"),
        "importance": body.get("metadata", {}).get("importance", "medium"),
        "confidence": float(body.get("metadata", {}).get("confidence", 0.6)),
        "retention_policy": "long_term",
        "tags": body.get("metadata", {}).get("tags", []),
    }
    return await _proxy("POST", "/api/v1/memories", json_body=payload)


@router.post("/rag/retrieve")
async def rag_retrieve(body: dict):
    search_body = {
        "tenant_id": body.get("tenant_id", "default"),
        "query": body.get("query", ""),
        "top_k": body.get("top_k", 5),
        "filters": {"status": "active"},
    }
    return await _proxy("POST", "/api/v1/memories/search", json_body=search_body)


@router.get("/memories")
async def list_memories(
    tenant_id: str = "default",
    status: str | None = None,
    type: str | None = None,  # noqa: A002
    tag: str | None = None,
    source: str | None = None,
    min_confidence: float | None = None,
):
    params = {
        "tenant_id": tenant_id,
        "status": status,
        "type": type,
        "tag": tag,
        "source": source,
        "min_confidence": min_confidence,
    }
    return await _proxy("GET", "/api/v1/memories", params=params)


@router.post("/memories")
async def create_memory(body: dict):
    return await _proxy("POST", "/api/v1/memories", json_body=body)


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str):
    return await _proxy("GET", f"/api/v1/memories/{memory_id}")


@router.post("/memories/search")
async def search_memories(body: dict):
    return await _proxy("POST", "/api/v1/memories/search", json_body=body)


@router.post("/memories/{memory_id}/merge")
async def merge_memory(memory_id: str, body: dict):
    return await _proxy("POST", f"/api/v1/memories/{memory_id}/merge", json_body=body)


@router.patch("/memories/{memory_id}/status")
async def update_memory_status(memory_id: str, body: dict):
    return await _proxy("PATCH", f"/api/v1/memories/{memory_id}/status", json_body=body)


@router.get("/resources/{resource_type}/{resource_id}/memories")
async def resource_memories(resource_type: str, resource_id: str, tenant_id: str = "default"):
    return await _proxy("GET", f"/api/v1/resources/{resource_type}/{resource_id}/memories", params={"tenant_id": tenant_id})


@router.get("/memory-policies")
async def list_memory_policies():
    return await _proxy("GET", "/api/v1/memory-policies")


@router.put("/memory-policies")
async def put_memory_policies(body: list[dict]):
    return await _proxy("PUT", "/api/v1/memory-policies", json_body=body)


@router.post("/memory/context")
async def memory_context(body: dict):
    return await _proxy("POST", "/api/v1/memory/context", json_body=body)


@router.post("/sop-candidates")
async def create_sop_candidate(body: dict):
    return await _proxy("POST", "/api/v1/sop-candidates", json_body=body)


@router.get("/sop-candidates")
async def list_sop_candidates(tenant_id: str = "default"):
    return await _proxy("GET", "/api/v1/sop-candidates", params={"tenant_id": tenant_id})


@router.post("/sop-candidates/{candidate_id}/promote")
async def promote_sop_candidate(candidate_id: str):
    return await _proxy("POST", f"/api/v1/sop-candidates/{candidate_id}/promote")
