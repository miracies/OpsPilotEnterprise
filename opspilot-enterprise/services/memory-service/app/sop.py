from __future__ import annotations

from opspilot_schema.memory import SopCandidate, SopCandidateCreateRequest

from app.service import MemoryService


def create_candidate(service: MemoryService, request: SopCandidateCreateRequest) -> SopCandidate:
    return service.store.create_sop_candidate(request)

