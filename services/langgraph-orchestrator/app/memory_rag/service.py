from __future__ import annotations

import os
from typing import Any

import httpx

from opspilot_schema.memory_rag import (
    MemoryUpsertRequest,
    MemoryUpsertResponse,
    RagHit,
    RagRetrieveRequest,
    RagRetrieveResponse,
)

from app.audit.events import append_audit_event
from app.storage.postgres import mirror_memory_to_sqlite, pg_enabled, recall_memory_items, upsert_memory_item, write_shadow_event

KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8072").rstrip("/")
MEMORY_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "http://127.0.0.1:8073").rstrip("/")


def upsert_memory(body: MemoryUpsertRequest) -> MemoryUpsertResponse:
    payload_for_service = {
        "tenant_id": body.tenant_id,
        "user_id": body.subject_id if body.scope == "user" else None,
        "memory_type": (body.metadata or {}).get("memory_type", "user_memory" if body.scope == "user" else "knowledge_memory"),
        "title": body.key,
        "summary": body.value_text,
        "content": {"legacy_memory": body.model_dump()},
        "source": body.source_ref or "orchestrator-memory-upsert",
        "importance": (body.metadata or {}).get("importance", "medium"),
        "confidence": float((body.metadata or {}).get("confidence", 0.6)),
        "retention_policy": "long_term",
        "tags": (body.metadata or {}).get("tags", []),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{MEMORY_SERVICE_URL}/api/v1/memories", json=payload_for_service)
        data = resp.json()
        item = data.get("data") or {}
        if data.get("success") and item.get("id"):
            return MemoryUpsertResponse(
                memory_id=str(item["id"]),
                version_no=1,
                scope=body.scope,
                subject_id=body.subject_id,
                key=body.key,
                created_at=str(item.get("created_at") or ""),
                storage_backend="postgres",
            )
    except Exception:
        pass

    payload = body.model_dump()
    meta = upsert_memory_item(payload)
    merged = {**payload, **meta}
    mirror_memory_to_sqlite(merged)
    write_shadow_event("memory_items", str(meta.get("memory_id")), merged)
    return MemoryUpsertResponse(
        memory_id=str(meta.get("memory_id")),
        version_no=int(meta.get("version_no") or 1),
        scope=body.scope,
        subject_id=body.subject_id,
        key=body.key,
        created_at=str(meta.get("created_at")),
        storage_backend="postgres" if pg_enabled() else "sqlite",
    )


async def _retrieve_knowledge(query: str, environment: str | None = None) -> list[dict[str, Any]]:
    params = {"status": "published", "q": query}
    if environment:
        params["environment"] = environment
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{KNOWLEDGE_SERVICE_URL}/knowledge/articles", params=params)
    body = resp.json()
    if not body.get("success"):
        return []
    data = body.get("data") or {}
    return data.get("items") or []


async def rag_retrieve(body: RagRetrieveRequest) -> RagRetrieveResponse:
    memory_hits: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_URL}/api/v1/memories/search",
                json={"tenant_id": body.tenant_id, "query": body.query, "top_k": max(1, body.top_k), "filters": {"status": "active"}},
            )
        data = resp.json()
        for hit in ((data.get("data") or {}).get("hits") or []):
            memory = hit.get("memory") or {}
            memory_hits.append(
                {
                    "memory_id": memory.get("id"),
                    "key": memory.get("title"),
                    "value_text": memory.get("summary"),
                    "source_ref": memory.get("source"),
                    "score": hit.get("score"),
                    "metadata": memory,
                }
            )
    except Exception:
        memory_hits = recall_memory_items(
            tenant_id=body.tenant_id,
            query=body.query,
            scopes=body.scopes,
            top_k=max(1, body.top_k),
        )
    kb_hits = await _retrieve_knowledge(body.query, environment=body.environment)

    hits: list[RagHit] = []
    for item in memory_hits[: body.top_k]:
        hits.append(
            RagHit(
                ref_id=str(item.get("memory_id")),
                source_type="memory",
                title=str(item.get("key") or "memory"),
                summary=str(item.get("value_text") or ""),
                score=float(item.get("score") or 0.5),
                source=str(item.get("source_ref") or "memory"),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            )
        )
    for item in kb_hits[: body.top_k]:
        hits.append(
            RagHit(
                ref_id=str(item.get("id") or ""),
                source_type="knowledge",
                title=str(item.get("title") or "knowledge"),
                summary=str(item.get("content_summary") or ""),
                score=float(item.get("relevance_score") or item.get("confidence_score") or 0.4),
                source="knowledge-service",
                metadata={"why_selected": item.get("why_selected", "")},
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[: max(1, body.top_k)]
    citations = [
        {
            "ref_id": hit.ref_id,
            "source_type": hit.source_type,
            "title": hit.title,
            "score": round(hit.score, 3),
        }
        for hit in hits
    ]
    evidence_refs = [hit.ref_id for hit in hits if hit.ref_id]
    insufficient = len(hits) == 0
    reason = "证据不足：未命中 memory 与知识库。" if insufficient else ""

    if body.run_id:
        append_audit_event(
            run_id=body.run_id,
            event_type="RAG_RETRIEVED",
            summary=f"RAG hits={len(hits)}",
            detail={"hits": [h.model_dump() for h in hits[:5]]},
        )
    return RagRetrieveResponse(
        query=body.query,
        hits=hits,
        citations=citations,
        evidence_refs=evidence_refs,
        insufficient_evidence=insufficient,
        reason=reason,
    )
