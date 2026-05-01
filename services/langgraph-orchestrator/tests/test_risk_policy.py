from __future__ import annotations

import os
import tempfile
import unittest

from app.policy.engine import RiskStrategyEngine
from app.storage.db import init_db
from opspilot_schema.policy_rule import RiskEvaluationInput


class RiskPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["ORCHESTRATOR_DB_PATH"] = os.path.join(self.tmpdir.name, "orchestrator.db")
        init_db()
        self.engine = RiskStrategyEngine(fresh=True) if False else RiskStrategyEngine()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()
        os.environ.pop("ORCHESTRATOR_DB_PATH", None)

    def test_readonly_is_l0(self):
        result = self.engine.evaluate(RiskEvaluationInput(domain="knowledge", action="answer_question", environment="prod"))
        self.assertEqual(result.risk_level, "L0")
        self.assertFalse(result.require_approval)

    def test_prod_write_requires_approval(self):
        result = self.engine.evaluate(RiskEvaluationInput(domain="vmware", action="vm_power", environment="prod", resource_scope="single"))
        self.assertEqual(result.risk_level, "L2")
        self.assertTrue(result.require_approval)
        self.assertNotIn("always", result.allowed_scopes)

    def test_destructive_is_denied(self):
        result = self.engine.evaluate(RiskEvaluationInput(domain="k8s", action="delete_pvc", environment="prod"))
        self.assertTrue(result.deny)
        self.assertEqual(result.risk_level, "L4")


if __name__ == "__main__":
    unittest.main()
