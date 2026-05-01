from __future__ import annotations

from opspilot_schema.memory import MemoryItem, MemoryMergeRequest

from app.service import MemoryService


def merge_memories(service: MemoryService, memory_id: str, request: MemoryMergeRequest) -> MemoryItem:
    return service.store.merge(memory_id, request)

