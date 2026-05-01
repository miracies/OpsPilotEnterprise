from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from app.memory_rag.service import rag_retrieve, upsert_memory
from app.storage.db import init_db
from opspilot_schema.memory_rag import MemoryUpsertRequest, RagRetrieveRequest


class MemoryRagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["ORCHESTRATOR_DB_PATH"] = os.path.join(self.tmpdir.name, "orchestrator.db")
        os.environ.pop("ORCHESTRATOR_POSTGRES_DSN", None)
        init_db()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()
        os.environ.pop("ORCHESTRATOR_DB_PATH", None)

    def test_memory_upsert_sqlite_fallback(self):
        res = upsert_memory(
            MemoryUpsertRequest(
                tenant_id="t1",
                scope="user",
                subject_id="u1",
                key="default_cluster",
                value_text="cluster-a",
                source_ref="manual",
            )
        )
        self.assertEqual(res.storage_backend, "sqlite")
        self.assertTrue(res.memory_id.startswith("mem_"))

    def test_rag_retrieve_memory_hit(self):
        upsert_memory(
            MemoryUpsertRequest(
                tenant_id="t1",
                scope="user",
                subject_id="u1",
                key="default_namespace",
                value_text="payment",
                source_ref="manual",
            )
        )
        with patch("app.memory_rag.service._retrieve_knowledge", return_value=[]):
            res = asyncio.run(
                rag_retrieve(
                    RagRetrieveRequest(
                        tenant_id="t1",
                        query="payment namespace",
                        top_k=5,
                    )
                )
            )
        self.assertGreaterEqual(len(res.hits), 1)
        self.assertFalse(res.insufficient_evidence)


if __name__ == "__main__":
    unittest.main()
