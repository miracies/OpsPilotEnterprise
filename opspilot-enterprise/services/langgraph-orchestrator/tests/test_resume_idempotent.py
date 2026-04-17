from __future__ import annotations

import os
import tempfile
import unittest

from app.audit.checkpoint import default_idempotency_key, upsert_checkpoint
from app.resume.service import resume_run
from app.storage.db import init_db
from opspilot_schema.resume import PlanStep, ResumeRequest


class ResumeIdempotentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["ORCHESTRATOR_DB_PATH"] = os.path.join(self.tmpdir.name, "orchestrator.db")
        init_db()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()
        os.environ.pop("ORCHESTRATOR_DB_PATH", None)

    def test_resume_skips_safe_steps(self):
        run_id = "run-test"
        step1 = PlanStep(seq=1, action="validate_context", args={})
        step2 = PlanStep(seq=2, action="vm_power", args={})
        upsert_checkpoint(run_id=run_id, step=step1, status="safe")
        upsert_checkpoint(run_id=run_id, step=step2, status="waiting")
        result = resume_run(run_id, ResumeRequest(mode="continue"))
        self.assertEqual(result.status, "resumed")
        self.assertEqual(result.resume_from_step, 2)
        self.assertEqual(result.skipped_steps, [1])
        self.assertEqual(default_idempotency_key(run_id, 2), f"{run_id}-step2")


if __name__ == "__main__":
    unittest.main()
