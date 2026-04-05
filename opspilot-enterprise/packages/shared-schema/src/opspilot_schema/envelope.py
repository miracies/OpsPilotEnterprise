from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    success: bool = True
    message: str = "ok"
    data: T | None = None
    error: str | None = None
    audit_ref: str | None = None
    trace_id: str = Field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def make_success(data: Any, **kwargs: Any) -> dict:
    return ApiEnvelope(data=data, **kwargs).model_dump()


def make_error(error: str, **kwargs: Any) -> dict:
    return ApiEnvelope(success=False, message="error", error=error, **kwargs).model_dump()
