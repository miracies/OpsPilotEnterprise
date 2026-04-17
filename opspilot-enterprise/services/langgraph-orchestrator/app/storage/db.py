"""SQLite storage for orchestrator MVP (intent recovery / interactions / audit / resume)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_db_path() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_DB_PATH", str(DATA_DIR / "orchestrator.db")))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


DDL_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS op_intent_runs (
        run_id            TEXT PRIMARY KEY,
        conversation_id   TEXT NOT NULL,
        user_id           TEXT NOT NULL,
        channel           TEXT NOT NULL,
        tenant_id         TEXT,
        raw_utterance     TEXT NOT NULL,
        normalized_text   TEXT NOT NULL,
        decision          TEXT NOT NULL,
        chosen_intent     TEXT,
        clarify_reasons   TEXT,
        rejected_reasons  TEXT,
        created_at        TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_intent_runs_conv ON op_intent_runs(conversation_id, user_id)",
    "CREATE INDEX IF NOT EXISTS idx_intent_runs_ts ON op_intent_runs(created_at)",
    """
    CREATE TABLE IF NOT EXISTS op_intent_candidates (
        run_id         TEXT NOT NULL,
        rank_no        INTEGER NOT NULL,
        intent_code    TEXT NOT NULL,
        domain_name    TEXT NOT NULL,
        action_name    TEXT NOT NULL,
        score          REAL NOT NULL,
        score_breakdown TEXT NOT NULL,
        slots_json     TEXT NOT NULL,
        missing_slots  TEXT,
        evidence_json  TEXT,
        inferred_risk  TEXT,
        created_at     TEXT NOT NULL,
        PRIMARY KEY (run_id, rank_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_intent_candidates_run ON op_intent_candidates(run_id)",
    """
    CREATE TABLE IF NOT EXISTS op_interactions (
        interaction_id TEXT PRIMARY KEY,
        run_id         TEXT NOT NULL,
        kind           TEXT NOT NULL,
        status         TEXT NOT NULL,
        payload_json   TEXT NOT NULL,
        response_json  TEXT,
        created_by     TEXT NOT NULL,
        responded_by   TEXT,
        created_at     TEXT NOT NULL,
        responded_at   TEXT,
        expires_at     TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_interactions_run_kind ON op_interactions(run_id, kind)",
    "CREATE INDEX IF NOT EXISTS idx_interactions_status ON op_interactions(status, expires_at)",
    """
    CREATE TABLE IF NOT EXISTS op_approval_requests (
        approval_id    TEXT PRIMARY KEY,
        run_id         TEXT NOT NULL,
        risk_level     TEXT NOT NULL,
        environment    TEXT NOT NULL,
        resource_scope_json TEXT NOT NULL,
        command_preview_json TEXT NOT NULL,
        plan_steps_json TEXT,
        rollback_plan_json TEXT,
        allowed_scopes_json TEXT NOT NULL,
        final_scope    TEXT,
        decision       TEXT,
        approved_by    TEXT,
        approved_at    TEXT,
        expires_at     TEXT,
        summary        TEXT NOT NULL,
        domain_name    TEXT NOT NULL,
        action_name    TEXT NOT NULL,
        created_at     TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_approvals_run ON op_approval_requests(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_risk_env ON op_approval_requests(risk_level, environment)",
    """
    CREATE TABLE IF NOT EXISTS op_policy_rules (
        rule_code      TEXT PRIMARY KEY,
        enabled        INTEGER NOT NULL DEFAULT 1,
        priority_no    INTEGER NOT NULL,
        matcher_json   TEXT NOT NULL,
        decision_json  TEXT NOT NULL,
        remark         TEXT,
        updated_at     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS op_audit_events (
        event_id    TEXT PRIMARY KEY,
        run_id      TEXT NOT NULL,
        step_no     INTEGER NOT NULL,
        event_type  TEXT NOT NULL,
        actor_type  TEXT NOT NULL,
        actor_id    TEXT NOT NULL,
        summary     TEXT NOT NULL,
        detail_json TEXT,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_run_step ON op_audit_events(run_id, step_no)",
    "CREATE INDEX IF NOT EXISTS idx_audit_type ON op_audit_events(event_type, created_at)",
    """
    CREATE TABLE IF NOT EXISTS op_resume_checkpoints (
        checkpoint_id  TEXT PRIMARY KEY,
        run_id         TEXT NOT NULL,
        step_no        INTEGER NOT NULL,
        step_hash      TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        status         TEXT NOT NULL,
        resume_payload_json TEXT NOT NULL,
        rollback_payload_json TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT,
        UNIQUE (run_id, step_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_checkpoints_run_status ON op_resume_checkpoints(run_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_checkpoints_idem ON op_resume_checkpoints(idempotency_key)",
]


def init_db() -> None:
    """Create tables if missing and seed default risk policy rules."""
    conn = get_db()
    try:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)
        _seed_policy_rules(conn)
    finally:
        conn.close()


def _seed_policy_rules(conn: sqlite3.Connection) -> None:
    from datetime import datetime, timezone

    from app.policy.rules import default_rules

    row = conn.execute("SELECT COUNT(*) AS n FROM op_policy_rules").fetchone()
    if row and row["n"] > 0:
        return
    now = datetime.now(timezone.utc).isoformat()
    for rule in default_rules():
        conn.execute(
            """
            INSERT INTO op_policy_rules(rule_code, enabled, priority_no, matcher_json, decision_json, remark, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.rule_code,
                1 if rule.enabled else 0,
                rule.priority,
                json.dumps(rule.matcher.model_dump(), ensure_ascii=False),
                json.dumps(rule.decision.model_dump(), ensure_ascii=False),
                rule.remark,
                now,
            ),
        )


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    conn = get_db()
    try:
        conn.execute(sql, tuple(params))
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    conn = get_db()
    try:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    conn = get_db()
    try:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
