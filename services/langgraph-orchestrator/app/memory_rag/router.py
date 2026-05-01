from __future__ import annotations

from fastapi import APIRouter

from opspilot_schema.envelope import make_success
from opspilot_schema.memory_rag import MemoryUpsertRequest, RagRetrieveRequest

from .service import rag_retrieve, upsert_memory

router = APIRouter(tags=["memory-rag"])


@router.post("/api/v1/memory/upsert")
async def memory_upsert_route(body: MemoryUpsertRequest):
    result = upsert_memory(body)
    return make_success(result.model_dump())


@router.post("/api/v1/rag/retrieve")
async def rag_retrieve_route(body: RagRetrieveRequest):
    result = await rag_retrieve(body)
    return make_success(result.model_dump())
