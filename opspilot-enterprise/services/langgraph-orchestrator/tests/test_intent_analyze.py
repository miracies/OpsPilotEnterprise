from __future__ import annotations

import os
import tempfile
import unittest

from app.intent_recovery.analyze_service import analyze_intent
from app.storage.db import init_db
from opspilot_schema.intent import IntentAnalyzeInput


class IntentAnalyzeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["ORCHESTRATOR_DB_PATH"] = os.path.join(self.tmpdir.name, "orchestrator.db")
        os.environ.pop("ORCHESTRATOR_POSTGRES_DSN", None)
        init_db()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()
        os.environ.pop("ORCHESTRATOR_DB_PATH", None)

    def test_execute_mode_for_explicit_action(self):
        result = analyze_intent(
            IntentAnalyzeInput(
                conversation_id="sess-a",
                user_id="u1",
                utterance="power on vm Test-VM prod",
            )
        )
        self.assertEqual(result.decision, "recovered")
        self.assertEqual(result.execution_intent.mode, "execute")

    def test_consult_phrase_block_execute(self):
        result = analyze_intent(
            IntentAnalyzeInput(
                conversation_id="sess-b",
                user_id="u1",
                utterance="先看看怎么重启service nginx",
            )
        )
        self.assertIn(result.execution_intent.mode, {"read", "plan"})
        self.assertIn("consult_to_execute_blocked", result.execution_intent.guardrails)


if __name__ == "__main__":
    unittest.main()
