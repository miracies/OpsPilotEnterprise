from __future__ import annotations

import os
from typing import Any

from opspilot_schema.memory import MemoryItem


class GraphAdapter:
    def __init__(self) -> None:
        self.uri = os.environ.get("NEO4J_URI", "").strip()
        self.user = os.environ.get("NEO4J_USER", "neo4j")
        self.password = os.environ.get("NEO4J_PASSWORD", "")
        self._driver: Any | None = None
        if self.uri:
            try:
                from neo4j import GraphDatabase  # type: ignore

                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            except Exception:
                self._driver = None

    def enabled(self) -> bool:
        return self._driver is not None

    def sync_memory(self, memory: MemoryItem) -> str:
        if not self._driver:
            return "degraded"
        try:
            with self._driver.session() as session:
                session.execute_write(self._write_memory, memory)
            return "synced"
        except Exception:
            return "degraded"

    @staticmethod
    def _write_memory(tx: Any, memory: MemoryItem) -> None:
        tx.run(
            """
            MERGE (m:Memory {id: $id})
            SET m.tenant_id = $tenant_id,
                m.memory_type = $memory_type,
                m.title = $title,
                m.summary = $summary,
                m.status = $status,
                m.confidence = $confidence,
                m.updated_at = $updated_at
            """,
            id=memory.id,
            tenant_id=memory.tenant_id,
            memory_type=memory.memory_type,
            title=memory.title,
            summary=memory.summary,
            status=memory.status,
            confidence=memory.confidence,
            updated_at=memory.updated_at,
        )
        for entity in memory.entities:
            entity_key = entity.entity_id or entity.entity_name or f"{entity.entity_type}:{memory.id}"
            tx.run(
                """
                MERGE (r:Resource {id: $entity_id, type: $entity_type})
                SET r.name = $entity_name
                WITH r
                MATCH (m:Memory {id: $memory_id})
                MERGE (m)-[:ABOUT_RESOURCE]->(r)
                """,
                memory_id=memory.id,
                entity_id=entity_key,
                entity_type=entity.entity_type,
                entity_name=entity.entity_name or entity_key,
            )
        root_cause = str(memory.content.get("root_cause") or "").strip()
        if root_cause:
            tx.run(
                """
                MERGE (rc:RootCause {description: $description})
                WITH rc
                MATCH (m:Memory {id: $memory_id})
                MERGE (m)-[:HAS_ROOT_CAUSE]->(rc)
                """,
                memory_id=memory.id,
                description=root_cause,
            )
        for action in memory.content.get("actions") or []:
            tx.run(
                """
                MERGE (a:Action {description: $description})
                WITH a
                MATCH (m:Memory {id: $memory_id})
                MERGE (m)-[:RESOLVED_BY]->(a)
                """,
                memory_id=memory.id,
                description=str(action),
            )

    def close(self) -> None:
        if self._driver:
            self._driver.close()

