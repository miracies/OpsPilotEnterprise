from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from opspilot_schema.resume import AuditEvent

from app.storage.db import execute, query_all


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(
    *,
    run_id: str,
    event_type: str,
    summary: str,
    step_no: int = 0,
    actor_type: str = "system",
    actor_id: str = "orchestrator",
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=f"ae_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        step_no=step_no,
        event_type=event_type,  # type: ignore[arg-type]
        actor_type=actor_type,  # type: ignore[arg-type]
        actor_id=actor_id,
        summary=summary,
        detail=detail or {},
        created_at=_now(),
    )
    execute(
        """
        INSERT INTO op_audit_events(event_id, run_id, step_no, event_type, actor_type, actor_id, summary, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            event.run_id,
            event.step_no,
            event.event_type,
            event.actor_type,
            event.actor_id,
            event.summary,
            json.dumps(event.detail, ensure_ascii=False),
            event.created_at,
        ),
    )
    return event


def list_audit_events(run_id: str) -> list[AuditEvent]:
    rows = query_all(
        "SELECT * FROM op_audit_events WHERE run_id=? ORDER BY step_no ASC, created_at ASC",
        (run_id,),
    )
    events: list[AuditEvent] = []
    for row in rows:
        events.append(
            AuditEvent(
                event_id=row["event_id"],
                run_id=row["run_id"],
                step_no=int(row["step_no"] or 0),
                event_type=row["event_type"],
                actor_type=row["actor_type"],
                actor_id=row["actor_id"],
                summary=row["summary"],
                detail=json.loads(row["detail_json"] or "{}"),
                created_at=row["created_at"],
            )
        )
    return events
