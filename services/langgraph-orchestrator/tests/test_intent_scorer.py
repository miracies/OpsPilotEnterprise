from __future__ import annotations

import os
import tempfile
import unittest

from app.intent_recovery.scorer import decide_score
from app.intent_recovery.service import recover
from app.storage.db import init_db
from opspilot_schema.intent import IntentRecoverInput


class IntentScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["ORCHESTRATOR_DB_PATH"] = os.path.join(self.tmpdir.name, "orchestrator.db")
        init_db()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()
        os.environ.pop("ORCHESTRATOR_DB_PATH", None)

    def test_recovered_when_high_score_and_gap_large(self):
        run = recover(IntentRecoverInput(conversation_id="sess-1", user_id="u1", utterance="power on vm Test-VM in prod"))
        self.assertEqual(run.decision, "recovered")
        self.assertEqual(run.chosen_intent.intent_code, "vmware.vm.power")

    def test_clarify_when_missing_slots(self):
        run = recover(IntentRecoverInput(conversation_id="sess-2", user_id="u1", utterance="restart service"))
        self.assertEqual(run.decision, "clarify_required")
        self.assertTrue(run.clarify_reasons)

    def test_decision_thresholds(self):
        self.assertEqual(decide_score(top1=0.8, top2=0.5, any_missing_slot=False), "recovered")
        self.assertEqual(decide_score(top1=0.6, top2=0.55, any_missing_slot=False), "clarify_required")
        self.assertEqual(decide_score(top1=0.2, top2=0.1, any_missing_slot=False), "rejected")


if __name__ == "__main__":
    unittest.main()
