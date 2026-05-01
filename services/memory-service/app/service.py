from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
import psycopg
from psycopg.rows import dict_row

from opspilot_schema.memory import (
    MemoryAgentAnalyzeRequest,
    MemoryAgentAnalyzeResponse,
    MemoryContextRequest,
    MemoryContextResponse,
    MemoryCreateRequest,
    MemoryEntity,
    MemoryEvidenceRef,
    MemoryItem,
    MemoryListResponse,
    MemoryMergeRequest,
    MemoryPolicyListResponse,
    MemoryPolicyRule,
    MemoryRelation,
    MemorySearchHit,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStatusUpdateRequest,
    SopCandidate,
    SopCandidateCreateRequest,
)

from app.extractor import extract_memory_candidates
from app.graph_adapter import GraphAdapter
from app.mem0_adapter import Mem0Adapter
from app.policy import MemoryPolicy, default_policy_rules

DATA_DIR = Path(os.environ.get("MEMORY_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class MemoryStore:
    def __init__(self) -> None:
        self.dsn = os.environ.get("MEMORY_POSTGRES_DSN") or os.environ.get("ORCHESTRATOR_POSTGRES_DSN") or ""
        self.sqlite_path = Path(os.environ.get("MEMORY_SQLITE_PATH", str(DATA_DIR / "memory.db")))

    def pg_enabled(self) -> bool:
        return bool(self.dsn.strip())

    def init(self) -> None:
        if self.pg_enabled():
            self._init_pg()
        else:
            self._init_sqlite()

    def _pg(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row)

    def _sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_pg(self) -> None:
        with self._pg() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                except Exception:
                    pass
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_item (
                        id TEXT PRIMARY KEY,
                        tenant_id VARCHAR(128) NOT NULL,
                        user_id VARCHAR(128),
                        memory_type VARCHAR(64) NOT NULL,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        content JSONB NOT NULL,
                        source VARCHAR(128) NOT NULL,
                        source_id VARCHAR(128),
                        importance VARCHAR(32) NOT NULL,
                        confidence NUMERIC(4,3) NOT NULL,
                        retention_policy VARCHAR(64) NOT NULL,
                        status VARCHAR(32) DEFAULT 'active',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        expire_at TIMESTAMPTZ NULL,
                        embedding DOUBLE PRECISION[]
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_item_type ON memory_item(tenant_id, memory_type, status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_item_source ON memory_item(source, source_id)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_entity (
                        id TEXT PRIMARY KEY,
                        memory_id TEXT NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
                        entity_type VARCHAR(64) NOT NULL,
                        entity_id VARCHAR(128),
                        entity_name VARCHAR(256),
                        properties JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_entity_lookup ON memory_entity(entity_type, entity_id)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_tag (
                        id TEXT PRIMARY KEY,
                        memory_id TEXT NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
                        tag VARCHAR(128) NOT NULL
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_tag ON memory_tag(tag)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_evidence_ref (
                        id TEXT PRIMARY KEY,
                        memory_id TEXT NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
                        evidence_id VARCHAR(128) NOT NULL,
                        evidence_type VARCHAR(64),
                        evidence_uri TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_relation (
                        id TEXT PRIMARY KEY,
                        source_memory_id TEXT NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
                        relation_type VARCHAR(64) NOT NULL,
                        target_type VARCHAR(64) NOT NULL,
                        target_id VARCHAR(128) NOT NULL,
                        weight NUMERIC(6,3) NOT NULL DEFAULT 1,
                        properties JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_policy (
                        id TEXT PRIMARY KEY,
                        payload_json JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_audit_log (
                        id TEXT PRIMARY KEY,
                        memory_id TEXT,
                        action VARCHAR(64) NOT NULL,
                        reason TEXT,
                        payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sop_candidate (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        source_memory_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                        recommended_steps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                        status TEXT NOT NULL DEFAULT 'candidate',
                        knowledge_article_id TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
        self.seed_policies(default_policy_rules())

    def _init_sqlite(self) -> None:
        conn = self._sqlite()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_item (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT,
                    memory_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    importance TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    retention_policy TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expire_at TEXT,
                    embedding_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_memory_item_type ON memory_item(tenant_id, memory_type, status);
                CREATE INDEX IF NOT EXISTS idx_memory_item_source ON memory_item(source, source_id);
                CREATE TABLE IF NOT EXISTS memory_entity (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    entity_name TEXT,
                    properties_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_entity_lookup ON memory_entity(entity_type, entity_id);
                CREATE TABLE IF NOT EXISTS memory_tag (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    tag TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_tag ON memory_tag(tag);
                CREATE TABLE IF NOT EXISTS memory_evidence_ref (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    evidence_type TEXT,
                    evidence_uri TEXT
                );
                CREATE TABLE IF NOT EXISTS memory_relation (
                    id TEXT PRIMARY KEY,
                    source_memory_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1,
                    properties_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_policy (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_audit_log (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT,
                    action TEXT NOT NULL,
                    reason TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sop_candidate (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source_memory_ids_json TEXT NOT NULL,
                    recommended_steps_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    knowledge_article_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
        finally:
            conn.close()
        self.seed_policies(default_policy_rules())

    def seed_policies(self, rules: list[MemoryPolicyRule]) -> None:
        if self.pg_enabled():
            with self._pg() as conn:
                with conn.cursor() as cur:
                    for rule in rules:
                        cur.execute(
                            """
                            INSERT INTO memory_policy(id, payload_json, updated_at)
                            VALUES (%s, %s::jsonb, NOW())
                            ON CONFLICT (id) DO NOTHING
                            """,
                            (rule.id, json.dumps(rule.model_dump(), ensure_ascii=False)),
                        )
            return
        conn = self._sqlite()
        try:
            for rule in rules:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO memory_policy(id, payload_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (rule.id, json.dumps(rule.model_dump(), ensure_ascii=False), _now()),
                )
        finally:
            conn.close()

    def list_policies(self) -> list[MemoryPolicyRule]:
        if self.pg_enabled():
            with self._pg() as conn:
                rows = conn.execute("SELECT payload_json FROM memory_policy ORDER BY id").fetchall()
            return [MemoryPolicyRule(**dict(row["payload_json"])) for row in rows]
        conn = self._sqlite()
        try:
            rows = conn.execute("SELECT payload_json FROM memory_policy ORDER BY id").fetchall()
            return [MemoryPolicyRule(**json.loads(row["payload_json"])) for row in rows]
        finally:
            conn.close()

    def replace_policies(self, rules: list[MemoryPolicyRule]) -> list[MemoryPolicyRule]:
        if self.pg_enabled():
            with self._pg() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM memory_policy")
                    for rule in rules:
                        payload = rule.model_dump()
                        payload["updated_at"] = _now()
                        cur.execute(
                            "INSERT INTO memory_policy(id, payload_json, updated_at) VALUES (%s, %s::jsonb, NOW())",
                            (rule.id, json.dumps(payload, ensure_ascii=False)),
                        )
        else:
            conn = self._sqlite()
            try:
                conn.execute("DELETE FROM memory_policy")
                for rule in rules:
                    payload = rule.model_dump()
                    payload["updated_at"] = _now()
                    conn.execute(
                        "INSERT INTO memory_policy(id, payload_json, updated_at) VALUES (?, ?, ?)",
                        (rule.id, json.dumps(payload, ensure_ascii=False), payload["updated_at"]),
                    )
            finally:
                conn.close()
        return self.list_policies()

    def create_memory(self, request: MemoryCreateRequest) -> MemoryItem:
        memory_id = _uid("mem")
        now = _now()
        if self.pg_enabled():
            with self._pg() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO memory_item(
                            id, tenant_id, user_id, memory_type, title, summary, content, source,
                            source_id, importance, confidence, retention_policy, status, created_at,
                            updated_at, expire_at, embedding
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,'active',NOW(),NOW(),%s::timestamptz,%s)
                        """,
                        (
                            memory_id,
                            request.tenant_id,
                            request.user_id,
                            request.memory_type,
                            request.title,
                            request.summary,
                            json.dumps(request.content, ensure_ascii=False),
                            request.source,
                            request.source_id,
                            request.importance,
                            request.confidence,
                            request.retention_policy,
                            request.expire_at,
                            request.embedding,
                        ),
                    )
                    self._replace_children_pg(cur, memory_id, request)
        else:
            conn = self._sqlite()
            try:
                conn.execute(
                    """
                    INSERT INTO memory_item(
                        id, tenant_id, user_id, memory_type, title, summary, content_json, source,
                        source_id, importance, confidence, retention_policy, status, created_at,
                        updated_at, expire_at, embedding_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        request.tenant_id,
                        request.user_id,
                        request.memory_type,
                        request.title,
                        request.summary,
                        json.dumps(request.content, ensure_ascii=False),
                        request.source,
                        request.source_id,
                        request.importance,
                        request.confidence,
                        request.retention_policy,
                        now,
                        now,
                        request.expire_at,
                        json.dumps(request.embedding or []),
                    ),
                )
                self._replace_children_sqlite(conn, memory_id, request)
            finally:
                conn.close()
        self.audit(memory_id, "create", "memory created", request.model_dump())
        item = self.get_memory(memory_id)
        if item is None:
            raise RuntimeError("memory create failed")
        return item

    def _replace_children_pg(self, cur: Any, memory_id: str, request: MemoryCreateRequest) -> None:
        for table in ("memory_entity", "memory_tag", "memory_evidence_ref", "memory_relation"):
            cur.execute(f"DELETE FROM {table} WHERE memory_id = %s" if table != "memory_relation" else f"DELETE FROM {table} WHERE source_memory_id = %s", (memory_id,))
        for entity in request.entities:
            cur.execute(
                """
                INSERT INTO memory_entity(id, memory_id, entity_type, entity_id, entity_name, properties)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                """,
                (_uid("ent"), memory_id, entity.entity_type, entity.entity_id, entity.entity_name, json.dumps(entity.properties, ensure_ascii=False)),
            )
        for tag in sorted(set(request.tags)):
            cur.execute("INSERT INTO memory_tag(id, memory_id, tag) VALUES (%s,%s,%s)", (_uid("tag"), memory_id, tag))
        for evidence in request.evidence_refs:
            cur.execute(
                "INSERT INTO memory_evidence_ref(id, memory_id, evidence_id, evidence_type, evidence_uri) VALUES (%s,%s,%s,%s,%s)",
                (_uid("ev"), memory_id, evidence.evidence_id, evidence.evidence_type, evidence.evidence_uri),
            )
        self._insert_derived_relations_pg(cur, memory_id, request)

    def _replace_children_sqlite(self, conn: sqlite3.Connection, memory_id: str, request: MemoryCreateRequest) -> None:
        for table, column in (("memory_entity", "memory_id"), ("memory_tag", "memory_id"), ("memory_evidence_ref", "memory_id"), ("memory_relation", "source_memory_id")):
            conn.execute(f"DELETE FROM {table} WHERE {column}=?", (memory_id,))
        for entity in request.entities:
            conn.execute(
                "INSERT INTO memory_entity(id, memory_id, entity_type, entity_id, entity_name, properties_json) VALUES (?, ?, ?, ?, ?, ?)",
                (_uid("ent"), memory_id, entity.entity_type, entity.entity_id, entity.entity_name, json.dumps(entity.properties, ensure_ascii=False)),
            )
        for tag in sorted(set(request.tags)):
            conn.execute("INSERT INTO memory_tag(id, memory_id, tag) VALUES (?, ?, ?)", (_uid("tag"), memory_id, tag))
        for evidence in request.evidence_refs:
            conn.execute(
                "INSERT INTO memory_evidence_ref(id, memory_id, evidence_id, evidence_type, evidence_uri) VALUES (?, ?, ?, ?, ?)",
                (_uid("ev"), memory_id, evidence.evidence_id, evidence.evidence_type, evidence.evidence_uri),
            )
        self._insert_derived_relations_sqlite(conn, memory_id, request)

    def _insert_derived_relations_pg(self, cur: Any, memory_id: str, request: MemoryCreateRequest) -> None:
        for entity in request.entities:
            target_id = entity.entity_id or entity.entity_name
            if target_id:
                cur.execute(
                    "INSERT INTO memory_relation(id, source_memory_id, relation_type, target_type, target_id, weight, properties) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (_uid("rel"), memory_id, "about_resource", entity.entity_type, target_id, 1.0, "{}"),
                )
        root_cause = str(request.content.get("root_cause") or "").strip()
        if root_cause:
            cur.execute(
                "INSERT INTO memory_relation(id, source_memory_id, relation_type, target_type, target_id, weight, properties) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (_uid("rel"), memory_id, "has_root_cause", "root_cause", root_cause[:128], 0.9, "{}"),
            )

    def _insert_derived_relations_sqlite(self, conn: sqlite3.Connection, memory_id: str, request: MemoryCreateRequest) -> None:
        for entity in request.entities:
            target_id = entity.entity_id or entity.entity_name
            if target_id:
                conn.execute(
                    "INSERT INTO memory_relation(id, source_memory_id, relation_type, target_type, target_id, weight, properties_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (_uid("rel"), memory_id, "about_resource", entity.entity_type, target_id, 1.0, "{}"),
                )
        root_cause = str(request.content.get("root_cause") or "").strip()
        if root_cause:
            conn.execute(
                "INSERT INTO memory_relation(id, source_memory_id, relation_type, target_type, target_id, weight, properties_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_uid("rel"), memory_id, "has_root_cause", "root_cause", root_cause[:128], 0.9, "{}"),
            )

    def get_memory(self, memory_id: str) -> MemoryItem | None:
        rows = self._query_items("WHERE mi.id = ?", [memory_id]) if not self.pg_enabled() else self._query_items("WHERE mi.id = %s", [memory_id])
        return rows[0] if rows else None

    def list_memories(self, *, tenant_id: str = "default", status: str | None = None, memory_type: str | None = None, tag: str | None = None, source: str | None = None, min_confidence: float | None = None) -> MemoryListResponse:
        conditions = ["mi.tenant_id = ?"]
        params: list[Any] = [tenant_id]
        if self.pg_enabled():
            conditions = ["mi.tenant_id = %s"]
        if status:
            conditions.append(f"mi.status = {'%s' if self.pg_enabled() else '?'}")
            params.append(status)
        if memory_type:
            conditions.append(f"mi.memory_type = {'%s' if self.pg_enabled() else '?'}")
            params.append(memory_type)
        if source:
            conditions.append(f"mi.source = {'%s' if self.pg_enabled() else '?'}")
            params.append(source)
        if min_confidence is not None:
            conditions.append(f"mi.confidence >= {'%s' if self.pg_enabled() else '?'}")
            params.append(min_confidence)
        if tag:
            conditions.append(f"EXISTS (SELECT 1 FROM memory_tag mt WHERE mt.memory_id = mi.id AND mt.tag = {'%s' if self.pg_enabled() else '?'})")
            params.append(tag)
        items = self._query_items("WHERE " + " AND ".join(conditions) + " ORDER BY mi.updated_at DESC LIMIT 300", params)
        return MemoryListResponse(items=items, total=len(items))

    def search(self, request: MemorySearchRequest) -> MemorySearchResponse:
        self.expire_due_memories()
        filters = request.filters
        conditions = ["mi.tenant_id = ?"]
        params: list[Any] = [request.tenant_id]
        placeholder = "?"
        if self.pg_enabled():
            conditions = ["mi.tenant_id = %s"]
            placeholder = "%s"
        if filters.status:
            conditions.append(f"mi.status = {placeholder}")
            params.append(filters.status)
        if filters.memory_type:
            conditions.append(f"mi.memory_type = {placeholder}")
            params.append(filters.memory_type)
        if filters.source:
            conditions.append(f"mi.source = {placeholder}")
            params.append(filters.source)
        if filters.min_confidence is not None:
            conditions.append(f"mi.confidence >= {placeholder}")
            params.append(filters.min_confidence)
        for tag in filters.tags:
            conditions.append(f"EXISTS (SELECT 1 FROM memory_tag mt WHERE mt.memory_id = mi.id AND mt.tag = {placeholder})")
            params.append(tag)
        if filters.entity_type:
            conditions.append(f"EXISTS (SELECT 1 FROM memory_entity me WHERE me.memory_id = mi.id AND me.entity_type = {placeholder})")
            params.append(filters.entity_type)
        if filters.entity_id:
            conditions.append(f"EXISTS (SELECT 1 FROM memory_entity me WHERE me.memory_id = mi.id AND me.entity_id = {placeholder})")
            params.append(filters.entity_id)
        items = self._query_items("WHERE " + " AND ".join(conditions) + " ORDER BY mi.updated_at DESC LIMIT 500", params)
        hits = self._rank_items(items, request.query, request.top_k)
        citations = [{"ref_id": h.memory.id, "title": h.memory.title, "score": round(h.score, 3)} for h in hits]
        return MemorySearchResponse(query=request.query, hits=hits, citations=citations)

    def _rank_items(self, items: list[MemoryItem], query: str, top_k: int) -> list[MemorySearchHit]:
        tokens = [t.lower() for t in re.split(r"[\s,;:/|]+", query or "") if t.strip()]
        hits: list[MemorySearchHit] = []
        for item in items:
            blob = " ".join(
                [
                    item.title,
                    item.summary,
                    json.dumps(item.content, ensure_ascii=False),
                    " ".join(item.tags),
                    " ".join(e.entity_name or e.entity_id or "" for e in item.entities),
                ]
            ).lower()
            score = 0.25 + float(item.confidence) * 0.35
            reasons: list[str] = []
            if not tokens and item.status == "active":
                score += 0.1
            for token in tokens:
                if token in blob:
                    score += 0.12
                    reasons.append(f"matched:{token}")
            if item.importance in {"high", "critical"}:
                score += 0.08
            if item.status == "downgraded":
                score -= 0.2
            if item.status in {"archived", "expired", "invalid", "deleted"}:
                score -= 0.5
            if score > 0.2:
                hits.append(MemorySearchHit(memory=item.model_copy(update={"score": round(score, 3)}), score=round(min(score, 0.99), 3), reasons=reasons or ["metadata_match"]))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(1, top_k)]

    def resource_memories(self, tenant_id: str, resource_type: str, resource_id: str) -> MemoryListResponse:
        placeholder = "%s" if self.pg_enabled() else "?"
        conditions = [
            f"mi.tenant_id = {placeholder}",
            f"mi.status IN ({placeholder}, {placeholder}, {placeholder})",
            f"EXISTS (SELECT 1 FROM memory_entity me WHERE me.memory_id = mi.id AND me.entity_type = {placeholder} AND (me.entity_id = {placeholder} OR me.entity_name = {placeholder}))",
        ]
        params = [tenant_id, "active", "downgraded", "archived", _normalize_resource_type(resource_type), resource_id, resource_id]
        items = self._query_items("WHERE " + " AND ".join(conditions) + " ORDER BY mi.updated_at DESC LIMIT 100", params)
        return MemoryListResponse(items=items, total=len(items))

    def update_status(self, memory_id: str, body: MemoryStatusUpdateRequest) -> MemoryItem:
        if self.pg_enabled():
            with self._pg() as conn:
                conn.execute(
                    "UPDATE memory_item SET status=%s, confidence=COALESCE(%s, confidence), updated_at=NOW() WHERE id=%s",
                    (body.status, body.confidence, memory_id),
                )
        else:
            conn = self._sqlite()
            try:
                conn.execute(
                    "UPDATE memory_item SET status=?, confidence=COALESCE(?, confidence), updated_at=? WHERE id=?",
                    (body.status, body.confidence, _now(), memory_id),
                )
            finally:
                conn.close()
        self.audit(memory_id, "status_update", body.reason or "", body.model_dump())
        item = self.get_memory(memory_id)
        if item is None:
            raise RuntimeError("memory not found")
        return item

    def merge(self, memory_id: str, body: MemoryMergeRequest) -> MemoryItem:
        source = self.get_memory(memory_id)
        target = self.get_memory(body.target_memory_id)
        if source is None or target is None:
            raise RuntimeError("source or target memory not found")
        if body.merge_strategy == "replace_summary":
            new_summary = source.summary
        else:
            new_summary = target.summary
        if body.merge_strategy == "append_evidence":
            existing = {e.evidence_id for e in target.evidence_refs}
            for evidence in source.evidence_refs:
                if evidence.evidence_id not in existing:
                    target.evidence_refs.append(evidence)
        if body.merge_strategy == "mark_duplicate":
            self.update_status(memory_id, MemoryStatusUpdateRequest(status="duplicate", reason=body.merge_reason))
        self._update_memory_content(target.id, summary=new_summary, content=target.content, evidence_refs=target.evidence_refs)
        self.audit(target.id, "merge", body.merge_reason, {"source_memory_id": memory_id, **body.model_dump()})
        merged = self.get_memory(target.id)
        if merged is None:
            raise RuntimeError("merge target not found")
        return merged

    def _update_memory_content(self, memory_id: str, *, summary: str, content: dict[str, Any], evidence_refs: list[MemoryEvidenceRef]) -> None:
        if self.pg_enabled():
            with self._pg() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE memory_item SET summary=%s, content=%s::jsonb, updated_at=NOW() WHERE id=%s", (summary, json.dumps(content, ensure_ascii=False), memory_id))
                    cur.execute("DELETE FROM memory_evidence_ref WHERE memory_id=%s", (memory_id,))
                    for evidence in evidence_refs:
                        cur.execute(
                            "INSERT INTO memory_evidence_ref(id, memory_id, evidence_id, evidence_type, evidence_uri) VALUES (%s,%s,%s,%s,%s)",
                            (_uid("ev"), memory_id, evidence.evidence_id, evidence.evidence_type, evidence.evidence_uri),
                        )
        else:
            conn = self._sqlite()
            try:
                conn.execute("UPDATE memory_item SET summary=?, content_json=?, updated_at=? WHERE id=?", (summary, json.dumps(content, ensure_ascii=False), _now(), memory_id))
                conn.execute("DELETE FROM memory_evidence_ref WHERE memory_id=?", (memory_id,))
                for evidence in evidence_refs:
                    conn.execute(
                        "INSERT INTO memory_evidence_ref(id, memory_id, evidence_id, evidence_type, evidence_uri) VALUES (?, ?, ?, ?, ?)",
                        (_uid("ev"), memory_id, evidence.evidence_id, evidence.evidence_type, evidence.evidence_uri),
                    )
            finally:
                conn.close()

    def create_sop_candidate(self, body: SopCandidateCreateRequest) -> SopCandidate:
        sop_id = _uid("sop")
        now = _now()
        if self.pg_enabled():
            with self._pg() as conn:
                conn.execute(
                    """
                    INSERT INTO sop_candidate(id, tenant_id, title, summary, source_memory_ids_json, recommended_steps_json, status, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,'candidate',NOW(),NOW())
                    """,
                    (sop_id, body.tenant_id, body.title, body.summary, json.dumps(body.source_memory_ids), json.dumps(body.recommended_steps)),
                )
        else:
            conn = self._sqlite()
            try:
                conn.execute(
                    """
                    INSERT INTO sop_candidate(id, tenant_id, title, summary, source_memory_ids_json, recommended_steps_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'candidate', ?, ?)
                    """,
                    (sop_id, body.tenant_id, body.title, body.summary, json.dumps(body.source_memory_ids), json.dumps(body.recommended_steps), now, now),
                )
            finally:
                conn.close()
        return self.get_sop_candidate(sop_id)

    def list_sop_candidates(self, tenant_id: str = "default") -> list[SopCandidate]:
        placeholder = "%s" if self.pg_enabled() else "?"
        if self.pg_enabled():
            with self._pg() as conn:
                rows = conn.execute(f"SELECT * FROM sop_candidate WHERE tenant_id={placeholder} ORDER BY updated_at DESC LIMIT 100", (tenant_id,)).fetchall()
        else:
            conn = self._sqlite()
            try:
                rows = conn.execute(f"SELECT * FROM sop_candidate WHERE tenant_id={placeholder} ORDER BY updated_at DESC LIMIT 100", (tenant_id,)).fetchall()
            finally:
                conn.close()
        return [self._sop_from_row(dict(row)) for row in rows]

    def get_sop_candidate(self, sop_id: str) -> SopCandidate:
        placeholder = "%s" if self.pg_enabled() else "?"
        if self.pg_enabled():
            with self._pg() as conn:
                row = conn.execute(f"SELECT * FROM sop_candidate WHERE id={placeholder}", (sop_id,)).fetchone()
        else:
            conn = self._sqlite()
            try:
                row = conn.execute(f"SELECT * FROM sop_candidate WHERE id={placeholder}", (sop_id,)).fetchone()
            finally:
                conn.close()
        if not row:
            raise RuntimeError("sop candidate not found")
        return self._sop_from_row(dict(row))

    def mark_sop_promoted(self, sop_id: str, article_id: str | None) -> SopCandidate:
        if self.pg_enabled():
            with self._pg() as conn:
                conn.execute("UPDATE sop_candidate SET status='promoted', knowledge_article_id=%s, updated_at=NOW() WHERE id=%s", (article_id, sop_id))
        else:
            conn = self._sqlite()
            try:
                conn.execute("UPDATE sop_candidate SET status='promoted', knowledge_article_id=?, updated_at=? WHERE id=?", (article_id, _now(), sop_id))
            finally:
                conn.close()
        return self.get_sop_candidate(sop_id)

    def _sop_from_row(self, row: dict[str, Any]) -> SopCandidate:
        return SopCandidate(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            source_memory_ids=_json_list(row.get("source_memory_ids_json")),
            recommended_steps=_json_list(row.get("recommended_steps_json")),
            status=str(row.get("status") or "candidate"),  # type: ignore[arg-type]
            knowledge_article_id=row.get("knowledge_article_id"),
            created_at=str(row.get("created_at") or _now()),
            updated_at=str(row.get("updated_at") or _now()),
        )

    def expire_due_memories(self) -> None:
        if self.pg_enabled():
            with self._pg() as conn:
                conn.execute("UPDATE memory_item SET status='expired', updated_at=NOW() WHERE expire_at IS NOT NULL AND expire_at < NOW() AND status='active'")
        else:
            conn = self._sqlite()
            try:
                conn.execute("UPDATE memory_item SET status='expired', updated_at=? WHERE expire_at IS NOT NULL AND expire_at < ? AND status='active'", (_now(), _now()))
            finally:
                conn.close()

    def audit(self, memory_id: str | None, action: str, reason: str, payload: dict[str, Any]) -> None:
        if self.pg_enabled():
            with self._pg() as conn:
                conn.execute(
                    "INSERT INTO memory_audit_log(id, memory_id, action, reason, payload_json, created_at) VALUES (%s,%s,%s,%s,%s::jsonb,NOW())",
                    (_uid("audit"), memory_id, action, reason, json.dumps(payload, ensure_ascii=False)),
                )
            return
        conn = self._sqlite()
        try:
            conn.execute(
                "INSERT INTO memory_audit_log(id, memory_id, action, reason, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (_uid("audit"), memory_id, action, reason, json.dumps(payload, ensure_ascii=False), _now()),
            )
        finally:
            conn.close()

    def _query_items(self, where_sql: str, params: Iterable[Any]) -> list[MemoryItem]:
        if self.pg_enabled():
            sql = f"""
                SELECT mi.*,
                       COALESCE((SELECT jsonb_agg(jsonb_build_object('id', me.id, 'entity_type', me.entity_type, 'entity_id', me.entity_id, 'entity_name', me.entity_name, 'properties', me.properties)) FROM memory_entity me WHERE me.memory_id = mi.id), '[]'::jsonb) AS entities_json,
                       COALESCE((SELECT jsonb_agg(mt.tag) FROM memory_tag mt WHERE mt.memory_id = mi.id), '[]'::jsonb) AS tags_json,
                       COALESCE((SELECT jsonb_agg(jsonb_build_object('id', ev.id, 'evidence_id', ev.evidence_id, 'evidence_type', ev.evidence_type, 'evidence_uri', ev.evidence_uri)) FROM memory_evidence_ref ev WHERE ev.memory_id = mi.id), '[]'::jsonb) AS evidence_json,
                       COALESCE((SELECT jsonb_agg(jsonb_build_object('id', mr.id, 'source_memory_id', mr.source_memory_id, 'relation_type', mr.relation_type, 'target_type', mr.target_type, 'target_id', mr.target_id, 'weight', mr.weight, 'properties', mr.properties)) FROM memory_relation mr WHERE mr.source_memory_id = mi.id), '[]'::jsonb) AS relations_json
                FROM memory_item mi
                {where_sql}
            """
            with self._pg() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._item_from_pg_row(dict(row)) for row in rows]
        sql = f"SELECT mi.* FROM memory_item mi {where_sql}"
        conn = self._sqlite()
        try:
            rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
            for row in rows:
                row["entities_json"] = [dict(r) for r in conn.execute("SELECT * FROM memory_entity WHERE memory_id=?", (row["id"],)).fetchall()]
                row["tags_json"] = [r["tag"] for r in conn.execute("SELECT tag FROM memory_tag WHERE memory_id=?", (row["id"],)).fetchall()]
                row["evidence_json"] = [dict(r) for r in conn.execute("SELECT * FROM memory_evidence_ref WHERE memory_id=?", (row["id"],)).fetchall()]
                row["relations_json"] = [dict(r) for r in conn.execute("SELECT * FROM memory_relation WHERE source_memory_id=?", (row["id"],)).fetchall()]
        finally:
            conn.close()
        return [self._item_from_sqlite_row(row) for row in rows]

    def _item_from_pg_row(self, row: dict[str, Any]) -> MemoryItem:
        return MemoryItem(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            user_id=row.get("user_id"),
            memory_type=str(row["memory_type"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            content=dict(row.get("content") or {}),
            source=str(row["source"]),
            source_id=row.get("source_id"),
            importance=str(row["importance"]),  # type: ignore[arg-type]
            confidence=float(row["confidence"]),
            retention_policy=str(row["retention_policy"]),  # type: ignore[arg-type]
            status=str(row.get("status") or "active"),  # type: ignore[arg-type]
            created_at=str(row.get("created_at") or _now()),
            updated_at=str(row.get("updated_at") or _now()),
            expire_at=str(row["expire_at"]) if row.get("expire_at") else None,
            entities=[MemoryEntity(**e) for e in (row.get("entities_json") or [])],
            tags=[str(t) for t in (row.get("tags_json") or [])],
            evidence_refs=[MemoryEvidenceRef(**e) for e in (row.get("evidence_json") or [])],
            relations=[MemoryRelation(**r) for r in (row.get("relations_json") or [])],
        )

    def _item_from_sqlite_row(self, row: dict[str, Any]) -> MemoryItem:
        return MemoryItem(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            user_id=row.get("user_id"),
            memory_type=str(row["memory_type"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            content=json.loads(row.get("content_json") or "{}"),
            source=str(row["source"]),
            source_id=row.get("source_id"),
            importance=str(row["importance"]),  # type: ignore[arg-type]
            confidence=float(row["confidence"]),
            retention_policy=str(row["retention_policy"]),  # type: ignore[arg-type]
            status=str(row.get("status") or "active"),  # type: ignore[arg-type]
            created_at=str(row.get("created_at") or _now()),
            updated_at=str(row.get("updated_at") or _now()),
            expire_at=row.get("expire_at"),
            entities=[
                MemoryEntity(
                    id=e.get("id"),
                    entity_type=e["entity_type"],
                    entity_id=e.get("entity_id"),
                    entity_name=e.get("entity_name"),
                    properties=json.loads(e.get("properties_json") or "{}"),
                )
                for e in (row.get("entities_json") or [])
            ],
            tags=[str(t) for t in (row.get("tags_json") or [])],
            evidence_refs=[MemoryEvidenceRef(**e) for e in (row.get("evidence_json") or [])],
            relations=[
                MemoryRelation(
                    id=r.get("id"),
                    source_memory_id=r["source_memory_id"],
                    relation_type=r["relation_type"],
                    target_type=r["target_type"],
                    target_id=r["target_id"],
                    weight=float(r.get("weight") or 1),
                    properties=json.loads(r.get("properties_json") or "{}"),
                )
                for r in (row.get("relations_json") or [])
            ],
        )


class MemoryService:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.graph = GraphAdapter()
        self.mem0 = Mem0Adapter()
        self.knowledge_url = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8072").rstrip("/")

    def init(self) -> None:
        self.store.init()

    async def create_memory(self, request: MemoryCreateRequest) -> MemoryItem:
        policy = MemoryPolicy(self.store.list_policies())
        decision = policy.validate(request)
        if not decision.allowed:
            raise ValueError(decision.reason)
        if request.embedding is None:
            request = request.model_copy(update={"embedding": self.mem0.fake_embedding(f"{request.title}\n{request.summary}")})
        item = self.store.create_memory(request)
        try:
            await self.mem0.add(memory_id=item.id, text=f"{item.title}\n{item.summary}", metadata=item.model_dump())
        except Exception:
            pass
        graph_status = self.graph.sync_memory(item)
        return item.model_copy(update={"graph_sync_status": graph_status})

    async def analyze(self, body: MemoryAgentAnalyzeRequest) -> MemoryAgentAnalyzeResponse:
        should_write, candidates, reason = extract_memory_candidates(body)
        written: list[MemoryItem] = []
        merge_candidates: list[MemorySearchHit] = []
        for candidate in candidates:
            search = self.store.search(
                MemorySearchRequest(
                    tenant_id=candidate.tenant_id,
                    query=f"{candidate.title} {candidate.summary}",
                    filters={"memory_type": candidate.memory_type, "status": "active"},  # type: ignore[arg-type]
                    top_k=3,
                )
            )
            merge_candidates.extend(search.hits)
            if body.auto_write and should_write:
                written.append(await self.create_memory(candidate))
        return MemoryAgentAnalyzeResponse(
            request_id=body.request_id,
            should_write_memory=should_write,
            memory_type=candidates[0].memory_type if candidates else None,
            importance=candidates[0].importance if candidates else "medium",
            confidence=candidates[0].confidence if candidates else 0.5,
            retention_policy=candidates[0].retention_policy if candidates else "long_term",
            memory_items=written,
            merge_candidates=merge_candidates,
            reason=reason,
        )

    def search(self, body: MemorySearchRequest) -> MemorySearchResponse:
        return self.store.search(body)

    def context(self, body: MemoryContextRequest) -> MemoryContextResponse:
        incident_hits = self.store.search(
            MemorySearchRequest(
                tenant_id=body.tenant_id,
                query=body.query,
                filters={"memory_type": "vmware_incident_memory", "status": "active", "tags": body.tags},  # type: ignore[arg-type]
                top_k=body.top_k,
            )
        ).hits
        resource_hits: list[MemorySearchHit] = []
        if body.resource_type and body.resource_id:
            resource_items = self.store.resource_memories(body.tenant_id, body.resource_type, body.resource_id).items
            resource_hits = self.store._rank_items(resource_items, body.query, body.top_k)

        risk_signals: list[str] = []
        actions: list[str] = []
        for hit in [*incident_hits, *resource_hits]:
            content = hit.memory.content
            root_cause = str(content.get("root_cause") or "").strip()
            if root_cause:
                risk_signals.append(f"Historical root cause: {root_cause}")
            for action in content.get("actions") or []:
                actions.append(str(action))
        citations = [{"ref_id": h.memory.id, "title": h.memory.title, "score": h.score} for h in [*incident_hits, *resource_hits]]
        return MemoryContextResponse(
            similar_incidents=incident_hits,
            resource_history=resource_hits,
            risk_signals=list(dict.fromkeys(risk_signals))[:10],
            recommended_actions=list(dict.fromkeys(actions))[:10],
            citations=citations,
        )

    async def promote_sop(self, sop_id: str) -> SopCandidate:
        sop = self.store.get_sop_candidate(sop_id)
        article_id: str | None = None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.knowledge_url}/knowledge/articles",
                    json={
                        "title": sop.title,
                        "content_summary": sop.summary,
                        "source": "memory-service",
                        "status": "published",
                        "tags": ["memory", "sop"],
                        "steps": sop.recommended_steps,
                    },
                )
                data = resp.json()
                article_id = str(((data.get("data") or {}).get("id")) or "") or None
        except Exception:
            article_id = None
        return self.store.mark_sop_promoted(sop_id, article_id)


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    try:
        return [str(v) for v in json.loads(value)]
    except Exception:
        return []


def _normalize_resource_type(value: str) -> str:
    lowered = (value or "").lower()
    if lowered in {"vmware.vm", "virtual_machine", "virtualmachine"}:
        return "vm"
    if lowered in {"vmware.host", "esxi", "hostsystem"}:
        return "host"
    return lowered.replace("vmware.", "") or "resource"

