from __future__ import annotations

from fastapi import APIRouter, Query

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.memory import (
    MemoryAgentAnalyzeRequest,
    MemoryContextRequest,
    MemoryCreateRequest,
    MemoryMergeRequest,
    MemoryPolicyRule,
    MemorySearchRequest,
    MemoryStatusUpdateRequest,
    SopCandidateCreateRequest,
)

from app.service import MemoryService

router = APIRouter()
service = MemoryService()


@router.post("/api/v1/memories")
async def create_memory(body: MemoryCreateRequest):
    try:
        item = await service.create_memory(body)
        return make_success(item.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/api/v1/memories")
async def list_memories(
    tenant_id: str = "default",
    status: str | None = None,
    type: str | None = Query(None),  # noqa: A002
    tag: str | None = None,
    source: str | None = None,
    min_confidence: float | None = None,
):
    try:
        result = service.store.list_memories(
            tenant_id=tenant_id,
            status=status,
            memory_type=type,
            tag=tag,
            source=source,
            min_confidence=min_confidence,
        )
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/api/v1/memories/{memory_id}")
async def get_memory(memory_id: str):
    try:
        item = service.store.get_memory(memory_id)
        if not item:
            return make_error(f"memory not found: {memory_id}")
        return make_success(item.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/memories/search")
async def search_memories(body: MemorySearchRequest):
    try:
        result = service.search(body)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/api/v1/resources/{resource_type}/{resource_id}/memories")
async def resource_memories(resource_type: str, resource_id: str, tenant_id: str = "default"):
    try:
        result = service.store.resource_memories(tenant_id, resource_type, resource_id)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/memories/{memory_id}/merge")
async def merge_memory(memory_id: str, body: MemoryMergeRequest):
    try:
        item = service.store.merge(memory_id, body)
        return make_success(item.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.patch("/api/v1/memories/{memory_id}/status")
async def update_memory_status(memory_id: str, body: MemoryStatusUpdateRequest):
    try:
        item = service.store.update_status(memory_id, body)
        return make_success(item.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/api/v1/memory-policies")
async def list_memory_policies():
    try:
        return make_success({"items": [r.model_dump() for r in service.store.list_policies()]})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.put("/api/v1/memory-policies")
async def put_memory_policies(body: list[MemoryPolicyRule]):
    try:
        rules = service.store.replace_policies(body)
        return make_success({"items": [r.model_dump() for r in rules]})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/memory-agent/analyze")
async def analyze_memory(body: MemoryAgentAnalyzeRequest):
    try:
        result = await service.analyze(body)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/memory/context")
async def memory_context(body: MemoryContextRequest):
    try:
        result = service.context(body)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/sop-candidates")
async def create_sop_candidate(body: SopCandidateCreateRequest):
    try:
        result = service.store.create_sop_candidate(body)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/api/v1/sop-candidates")
async def list_sop_candidates(tenant_id: str = "default"):
    try:
        items = service.store.list_sop_candidates(tenant_id)
        return make_success({"items": [item.model_dump() for item in items], "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/api/v1/sop-candidates/{candidate_id}/promote")
async def promote_sop_candidate(candidate_id: str):
    try:
        result = await service.promote_sop(candidate_id)
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))

