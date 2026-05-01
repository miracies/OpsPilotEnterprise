from __future__ import annotations

from opspilot_schema.memory import MemorySearchRequest, MemorySearchResponse

from app.service import MemoryService


def retrieve_memories(service: MemoryService, request: MemorySearchRequest) -> MemorySearchResponse:
    return service.search(request)

