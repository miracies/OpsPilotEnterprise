from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from opspilot_schema.resume import CheckpointRecord, PlanStep

from app.storage.db import execute, query_all, query_one


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_step_hash(run_id: str, step: PlanStep) -> str:
    payload = f"{run_id}|{step.seq}|{step.action}|{json.dumps(step.args, ensure_ascii=False, sort_keys=True)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_idempotency_key(run_id: str, seq: int) -> str:
    return f"{run_id}-step{seq}"


def upsert_checkpoint(
    *,
    run_id: str,
    step: PlanStep,
    status: str,
    resume_payload: dict[str, Any] | None = None,
    rollback_payload: dict[str, Any] | None = None,
) -> CheckpointRecord:
    checkpoint = CheckpointRecord(
        checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        step_no=step.seq,
        step_hash=build_step_hash(run_id, step),
        idempotency_key=step.idempotency_key or default_idempotency_key(run_id, step.seq),
        status=status,  # type: ignore[arg-type]
        resume_payload=resume_payload or step.args,
        rollback_payload=rollback_payload or {},
        created_at=_now(),
        updated_at=_now(),
    )
    existing = query_one("SELECT checkpoint_id, created_at FROM op_resume_checkpoints WHERE run_id=? AND step_no=?", (run_id, step.seq))
    if existing:
        checkpoint.checkpoint_id = existing["checkpoint_id"]
        checkpoint.created_at = existing["created_at"]
        execute(
            """
            UPDATE op_resume_checkpoints
            SET step_hash=?, idempotency_key=?, status=?, resume_payload_json=?, rollback_payload_json=?, updated_at=?
            WHERE run_id=? AND step_no=?
            """,
            (
                checkpoint.step_hash,
                checkpoint.idempotency_key,
                checkpoint.status,
                json.dumps(checkpoint.resume_payload, ensure_ascii=False),
                json.dumps(checkpoint.rollback_payload, ensure_ascii=False),
                checkpoint.updated_at,
                run_id,
                step.seq,
            ),
        )
    else:
        execute(
            """
            INSERT INTO op_resume_checkpoints(
                checkpoint_id, run_id, step_no, step_hash, idempotency_key, status,
                resume_payload_json, rollback_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint.checkpoint_id,
                checkpoint.run_id,
                checkpoint.step_no,
                checkpoint.step_hash,
                checkpoint.idempotency_key,
                checkpoint.status,
                json.dumps(checkpoint.resume_payload, ensure_ascii=False),
                json.dumps(checkpoint.rollback_payload, ensure_ascii=False),
                checkpoint.created_at,
                checkpoint.updated_at,
            ),
        )
    return checkpoint


def list_checkpoints(run_id: str) -> list[CheckpointRecord]:
    rows = query_all(
        "SELECT * FROM op_resume_checkpoints WHERE run_id=? ORDER BY step_no ASC",
        (run_id,),
    )
    return [
        CheckpointRecord(
            checkpoint_id=row["checkpoint_id"],
            run_id=row["run_id"],
            step_no=int(row["step_no"]),
            step_hash=row["step_hash"],
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            resume_payload=json.loads(row["resume_payload_json"] or "{}"),
            rollback_payload=json.loads(row["rollback_payload_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
