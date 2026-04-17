from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from opspilot_schema.interaction import ClarifyAnswerRequest, ClarifyCreateRequest, ClarifyRecord

from app.storage.db import execute, query_one


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def create_clarify(body: ClarifyCreateRequest) -> ClarifyRecord:
    record = ClarifyRecord(
        interaction_id=f"cl_{uuid.uuid4().hex[:12]}",
        run_id=body.run_id,
        question=body.question,
        choices=body.choices,
        allow_free_text=body.allow_free_text,
        reason_code=body.reason_code,
        status="pending",
        expires_at=_expires(body.expires_in_seconds),
        created_at=_now(),
    )
    execute(
        """
        INSERT INTO op_interactions(interaction_id, run_id, kind, status, payload_json, response_json, created_by, created_at, expires_at)
        VALUES (?, ?, 'clarify', ?, ?, NULL, ?, ?, ?)
        """,
        (
            record.interaction_id,
            record.run_id,
            record.status,
            json.dumps(record.model_dump(), ensure_ascii=False),
            record.created_by,
            record.created_at,
            record.expires_at,
        ),
    )
    return record


def answer_clarify(interaction_id: str, body: ClarifyAnswerRequest) -> ClarifyRecord:
    row = query_one("SELECT * FROM op_interactions WHERE interaction_id=? AND kind='clarify'", (interaction_id,))
    if not row:
        raise ValueError(f"Clarify interaction {interaction_id} not found")
    payload = json.loads(row["payload_json"] or "{}")
    record = ClarifyRecord(**payload)
    record.status = "answered"
    record.selected_choice = body.selected_choice
    record.free_text = body.free_text
    record.responded_at = _now()
    record.responded_by = body.responded_by
    execute(
        """
        UPDATE op_interactions
        SET status='answered', response_json=?, responded_by=?, responded_at=?
        WHERE interaction_id=?
        """,
        (
            json.dumps(
                {
                    "selected_choice": body.selected_choice,
                    "free_text": body.free_text,
                    "responded_by": body.responded_by,
                    "submitted_at": record.responded_at,
                },
                ensure_ascii=False,
            ),
            body.responded_by,
            record.responded_at,
            interaction_id,
        ),
    )
    return record
