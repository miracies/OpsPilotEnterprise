from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.storage.db import get_db_path

_MEMORY_CACHE: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_postgres_dsn() -> str:
    return os.environ.get("ORCHESTRATOR_POSTGRES_DSN", "").strip()


def pg_enabled() -> bool:
    return bool(get_postgres_dsn())


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(get_postgres_dsn(), autocommit=True, row_factory=dict_row)


def init_postgres() -> None:
    if not pg_enabled():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            vector_available = True
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception:
                # Extension can be unavailable in non-pgvector deployments.
                vector_available = False
            embedding_type = "vector(1536)" if vector_available else "DOUBLE PRECISION[]"
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS op_shadow_events (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_shadow_entity ON op_shadow_events(entity_type, entity_id)")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS memory_items (
                    memory_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_text TEXT NOT NULL,
                    source_ref TEXT DEFAULT '',
                    pii_level TEXT DEFAULT 'none',
                    retention_until TIMESTAMPTZ,
                    version_no INTEGER NOT NULL DEFAULT 1,
                    metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding {embedding_type},
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_scope_subject ON memory_items(tenant_id, scope, subject_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_key ON memory_items(tenant_id, key)")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding {embedding_type},
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON rag_chunks(tenant_id, source_type, source_ref)")


def write_shadow_event(entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
    if not pg_enabled():
        return
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO op_shadow_events(id, entity_type, entity_id, payload_json, created_at)
                    VALUES (%s, %s, %s, %s::jsonb, NOW())
                    """,
                    (f"se_{uuid.uuid4().hex[:12]}", entity_type, entity_id, json.dumps(payload, ensure_ascii=False)),
                )
    except Exception:
        return


def _sqlite_memory_upsert(payload: dict[str, Any]) -> dict[str, Any]:
    memory_id = payload.get("memory_id") or f"mem_{uuid.uuid4().hex[:12]}"
    payload["memory_id"] = memory_id
    payload["updated_at"] = _now()
    if memory_id not in _MEMORY_CACHE:
        payload["created_at"] = payload["updated_at"]
        payload["version_no"] = 1
    else:
        payload["created_at"] = _MEMORY_CACHE[memory_id].get("created_at") or payload["updated_at"]
        payload["version_no"] = int(_MEMORY_CACHE[memory_id].get("version_no") or 1) + 1
    _MEMORY_CACHE[memory_id] = payload
    return payload


def upsert_memory_item(payload: dict[str, Any]) -> dict[str, Any]:
    if not pg_enabled():
        return _sqlite_memory_upsert(payload)
    memory_id = str(payload.get("memory_id") or f"mem_{uuid.uuid4().hex[:12]}")
    tenant_id = str(payload.get("tenant_id") or "default")
    scope = str(payload.get("scope") or "user")
    subject_id = str(payload.get("subject_id") or "unknown")
    key = str(payload.get("key") or "unknown")
    value_text = str(payload.get("value_text") or "")
    source_ref = str(payload.get("source_ref") or "")
    pii_level = str(payload.get("pii_level") or "none")
    retention_until = payload.get("retention_until")
    metadata_obj = dict(payload.get("metadata") or {})
    embedding = payload.get("embedding")
    # Keep pgvector writes optional and non-blocking for MVP compatibility.
    if isinstance(embedding, list):
        metadata_obj["embedding_dim"] = len(embedding)
        embedding = None
    metadata_json = json.dumps(metadata_obj, ensure_ascii=False)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_items(
                    memory_id, tenant_id, scope, subject_id, key, value_text, source_ref,
                    pii_level, retention_until, metadata_json, embedding, created_at, updated_at, version_no
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s::timestamptz, %s::jsonb, %s, NOW(), NOW(), 1
                )
                ON CONFLICT (memory_id) DO UPDATE
                SET value_text = EXCLUDED.value_text,
                    source_ref = EXCLUDED.source_ref,
                    pii_level = EXCLUDED.pii_level,
                    retention_until = EXCLUDED.retention_until,
                    metadata_json = EXCLUDED.metadata_json,
                    embedding = COALESCE(EXCLUDED.embedding, memory_items.embedding),
                    updated_at = NOW(),
                    version_no = memory_items.version_no + 1
                RETURNING memory_id, version_no, created_at, updated_at
                """,
                (
                    memory_id,
                    tenant_id,
                    scope,
                    subject_id,
                    key,
                    value_text,
                    source_ref,
                    pii_level,
                    retention_until,
                    metadata_json,
                    embedding,
                ),
            )
            row = cur.fetchone() or {}
    return {
        "memory_id": row.get("memory_id", memory_id),
        "version_no": int(row.get("version_no") or 1),
        "created_at": str(row.get("created_at") or _now()),
        "updated_at": str(row.get("updated_at") or _now()),
    }


def recall_memory_items(*, tenant_id: str, query: str, scopes: list[str], top_k: int) -> list[dict[str, Any]]:
    if not pg_enabled():
        q = query.lower().strip()
        items = []
        for item in _MEMORY_CACHE.values():
            if str(item.get("tenant_id")) != tenant_id:
                continue
            if scopes and str(item.get("scope")) not in scopes:
                continue
            text = f"{item.get('key', '')} {item.get('value_text', '')}".lower()
            score = 0.0
            for token in q.split():
                if token and token in text:
                    score += 0.2
            if score > 0:
                items.append({**item, "score": min(0.99, score + 0.4)})
        items.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        return items[:max(1, top_k)]

    tokens = [token.strip() for token in query.split() if token.strip()]
    if not tokens:
        return []
    clauses = " OR ".join(["value_text ILIKE %s OR key ILIKE %s" for _ in tokens])
    params: list[Any] = [tenant_id]
    if scopes:
        params.append(tuple(scopes))
    like_params: list[Any] = []
    for token in tokens:
        like = f"%{token}%"
        like_params.extend([like, like])
    params.extend(like_params)
    params.append(max(1, top_k))
    scope_sql = "AND scope = ANY(%s)" if scopes else ""
    sql = f"""
        SELECT memory_id, tenant_id, scope, subject_id, key, value_text, source_ref, pii_level, metadata_json, created_at, updated_at
        FROM memory_items
        WHERE tenant_id = %s
          {scope_sql}
          AND ({clauses})
        ORDER BY updated_at DESC
        LIMIT %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
    hits: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        hits.append(
            {
                "memory_id": row.get("memory_id"),
                "tenant_id": row.get("tenant_id"),
                "scope": row.get("scope"),
                "subject_id": row.get("subject_id"),
                "key": row.get("key"),
                "value_text": row.get("value_text"),
                "source_ref": row.get("source_ref"),
                "pii_level": row.get("pii_level"),
                "metadata": row.get("metadata_json") or {},
                "created_at": str(row.get("created_at") or _now()),
                "updated_at": str(row.get("updated_at") or _now()),
                "score": round(max(0.2, 0.95 - idx * 0.08), 3),
            }
        )
    return hits


def sqlite_memory_snapshot_path() -> str:
    db_path = str(get_db_path())
    return db_path


def ensure_sqlite_memory_table() -> None:
    conn = sqlite3.connect(sqlite_memory_snapshot_path(), isolation_level=None, check_same_thread=False)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS op_memory_items (
                memory_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    finally:
        conn.close()


def mirror_memory_to_sqlite(payload: dict[str, Any]) -> None:
    ensure_sqlite_memory_table()
    conn = sqlite3.connect(sqlite_memory_snapshot_path(), isolation_level=None, check_same_thread=False)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO op_memory_items(memory_id, payload_json, updated_at)
            VALUES(?, ?, ?)
            """,
            (
                str(payload.get("memory_id") or ""),
                json.dumps(payload, ensure_ascii=False),
                _now(),
            ),
        )
    finally:
        conn.close()
