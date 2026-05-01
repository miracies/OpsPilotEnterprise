from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

AuditEventType = Literal[
    "RECOVER",
    "CONTEXT_COMPLETED",
    "NORMALIZED",
    "DISAMBIGUATED",
    "EXECUTION_INTENT_SET",
    "MEMORY_HIT",
    "RAG_RETRIEVED",
    "CLARIFY_CREATED",
    "CLARIFY_ANSWERED",
    "APPROVE_CREATED",
    "APPROVE_DECIDED",
    "PLAN",
    "PRE_EXEC",
    "POST_EXEC",
    "RESUME",
    "ROLLBACK",
    "FAILED",
    "COMPLETE",
    "vmware_kb_search_started",
    "vmware_kb_search_completed",
    "vmware_kb_search_no_hit",
    "vmware_kb_search_failed",
    "generic_qa_started",
    "generic_qa_retrieved",
    "generic_qa_completed",
    "generic_qa_fallback",
]
ActorType = Literal["user", "system", "agent", "tool"]
CheckpointStatus = Literal["safe", "waiting", "failed", "rolled_back"]
ResumeMode = Literal["continue", "rollback"]


class AuditEvent(BaseModel):
    event_id: str
    run_id: str
    step_no: int = 0
    event_type: AuditEventType
    actor_type: ActorType = "system"
    actor_id: str = "orchestrator"
    summary: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class CheckpointRecord(BaseModel):
    checkpoint_id: str
    run_id: str
    step_no: int
    step_hash: str
    idempotency_key: str
    status: CheckpointStatus = "waiting"
    resume_payload: dict[str, Any] = Field(default_factory=dict)
    rollback_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: Optional[str] = None


class PlanStep(BaseModel):
    seq: int
    type: Literal["read", "write", "wait", "conditional_write"] = "write"
    action: str
    args: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    wait_minutes: int = 0


class ResumeRequest(BaseModel):
    checkpoint_id: Optional[str] = None
    mode: ResumeMode = "continue"


class ResumeResponse(BaseModel):
    run_id: str
    status: Literal["resumed", "rolled_back", "nothing_to_resume", "rejected"]
    resume_from_step: Optional[int] = None
    skipped_steps: list[int] = Field(default_factory=list)
    message: str = ""
    last_safe_step: Optional[int] = None
    resume_from: Optional[str] = None
    rollback_available: bool = False
    decision_chain: list[str] = Field(default_factory=list)
    tool_outputs: list[str] = Field(default_factory=list)
