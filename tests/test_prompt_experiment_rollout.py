from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from data.db_client import DBClient
from data.repositories.prompt_diagnostics_repo import PromptDiagnosticsRepository


class TestPromptExperimentRollout(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "mawi-test.db"
        self.repo = PromptDiagnosticsRepository(db=DBClient(db_path))

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_shadow_assignment_keeps_effective_control_variant(self) -> None:
        assignment = self.repo.assign_variant(run_id="run-shadow", workflow_id="deal_followup_workflow")
        self.assertEqual(assignment["rollout_phase"], "shadow")
        self.assertEqual(assignment["effective_variant"], "A")

    def test_report_includes_variant_metrics(self) -> None:
        self.repo.assign_variant(run_id="run-metrics", workflow_id="deal_followup_workflow")
        self.repo.record_outcome_metrics(
            run_id="run-metrics",
            reply_received=True,
            meeting_booked=False,
            execution_success=True,
        )
        report = self.repo.diagnostics_report(limit=10)
        self.assertIn("experiments", report)
        self.assertIn("variant_metrics", report["experiments"])
        self.assertGreaterEqual(len(report["experiments"]["variant_metrics"]), 1)

    def test_degradation_triggers_auto_rollback(self) -> None:
        workflow_id = "deal_followup_workflow"
        now = "2026-01-01T00:00:00+00:00"
        with self.repo.db.tx() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_variant_rollouts (
                    workflow_id, rollout_phase, canary_percent, degradation_reply_threshold,
                    degradation_meeting_threshold, degradation_execution_threshold,
                    degradation_rejection_threshold, promoted_default_variant, updated_at
                ) VALUES (?, 'canary', 1.0, 0.05, 0.03, 0.05, 0.05, 'A', ?)
                """,
                (workflow_id, now),
            )

        for idx in range(12):
            run_a = f"run-a-{idx}"
            run_b = f"run-b-{idx}"
            with self.repo.db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO prompt_variant_assignments (
                        run_id, workflow_id, bucket, assigned_variant, effective_variant, rollout_phase, created_at
                    ) VALUES (?, ?, 'A', 'A', 'A', 'canary', ?)
                    """,
                    (run_a, workflow_id, now),
                )
                conn.execute(
                    """
                    INSERT INTO prompt_variant_assignments (
                        run_id, workflow_id, bucket, assigned_variant, effective_variant, rollout_phase, created_at
                    ) VALUES (?, ?, 'B', 'B', 'B', 'canary', ?)
                    """,
                    (run_b, workflow_id, now),
                )
            self.repo.record_outcome_metrics(
                run_id=run_a,
                reply_received=True,
                meeting_booked=True,
                execution_success=True,
            )
            self.repo.record_outcome_metrics(
                run_id=run_b,
                reply_received=False,
                meeting_booked=False,
                execution_success=False,
            )

        report = self.repo.diagnostics_report(limit=20)
        rollouts = {row["workflow_id"]: row for row in report["experiments"]["rollouts"]}
        self.assertEqual(rollouts[workflow_id]["rollout_phase"], "shadow")

    def test_promotion_requires_approval_gate(self) -> None:
        workflow_id = "deal_followup_workflow"
        self.repo.register_prompt_release(
            release_id="release-2026-04-11",
            workflow_id=workflow_id,
            workflow_release_version="2026.04.1",
            prompt_profile_version="1.1.0",
            owner="prompt-governance@mawi",
            status="active",
            changelog_note="Promote governed prompt registry set.",
        )
        with self.repo.db.tx() as conn:
            conn.execute(
                """
                UPDATE prompt_variant_rollouts
                SET rollout_phase='canary', canary_percent=1.0, promoted_default_variant='A'
                WHERE workflow_id=?
                """,
                (workflow_id,),
            )

        for idx in range(30):
            run_a = f"run-pa-{idx}"
            run_b = f"run-pb-{idx}"
            with self.repo.db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO prompt_variant_assignments (
                        run_id, workflow_id, bucket, assigned_variant, effective_variant, rollout_phase, created_at
                    ) VALUES (?, ?, 'A', 'A', 'A', 'canary', ?)
                    """,
                    (run_a, workflow_id, "2026-01-01T00:00:00+00:00"),
                )
                conn.execute(
                    """
                    INSERT INTO prompt_variant_assignments (
                        run_id, workflow_id, bucket, assigned_variant, effective_variant, rollout_phase, created_at
                    ) VALUES (?, ?, 'B', 'B', 'B', 'canary', ?)
                    """,
                    (run_b, workflow_id, "2026-01-01T00:00:00+00:00"),
                )
            self.repo.record_outcome_metrics(run_id=run_a, reply_received=False, meeting_booked=False, execution_success=False)
            self.repo.record_outcome_metrics(run_id=run_b, reply_received=True, meeting_booked=True, execution_success=True)

        report = self.repo.diagnostics_report(limit=20)
        rollouts = {row["workflow_id"]: row for row in report["experiments"]["rollouts"]}
        self.assertNotEqual(rollouts[workflow_id]["rollout_phase"], "full")

        self.repo.record_promotion_approval(
            workflow_id=workflow_id,
            release_id="release-2026-04-11",
            approver="owner-1@mawi",
            decision="approved",
            note="SLOs healthy.",
        )
        self.repo.record_promotion_approval(
            workflow_id=workflow_id,
            release_id="release-2026-04-11",
            approver="owner-2@mawi",
            decision="approved",
            note="Business sign-off complete.",
        )
        self.repo.record_outcome_metrics(run_id="run-pb-0", reply_received=True, meeting_booked=True, execution_success=True)

        report = self.repo.diagnostics_report(limit=20)
        rollouts = {row["workflow_id"]: row for row in report["experiments"]["rollouts"]}
        self.assertEqual(rollouts[workflow_id]["rollout_phase"], "full")


if __name__ == "__main__":
    unittest.main()
