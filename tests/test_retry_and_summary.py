import tempfile
import unittest
from pathlib import Path

from data.db_client import DBClient
from data.repositories.workflow_repo import WorkflowRepository
from orchestrator.retry_policy import with_retries


class TestRetryPolicy(unittest.TestCase):
    def test_with_retries_uses_backoff_and_terminal_tagging(self) -> None:
        attempts = {"count": 0}
        retries: list[int] = []

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient")
            return "ok"

        result = with_retries(
            flaky,
            retries=2,
            backoff_seconds=0.0,
            on_retry=lambda attempt, _exc, _delay: retries.append(attempt),
        )

        self.assertEqual(result, "ok")
        self.assertEqual(retries, [1])

        with self.assertRaises(ValueError) as ctx:
            with_retries(
                lambda: (_ for _ in ()).throw(ValueError("bad config")),
                retries=3,
                terminal_error_classes=(ValueError,),
            )
        self.assertTrue(getattr(ctx.exception, "terminal_retry_error", False))


class TestWorkflowSummary(unittest.TestCase):
    def test_get_run_summary_returns_latest_for_deal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = DBClient(Path(tmp) / "mawi.db")
            repo = WorkflowRepository(db=db)
            repo.create_or_update_deal("deal-1", {"account": "ACME"})
            run_id = repo.create_run("deal-1", "wf-1", "initialized", "running")
            repo.update_run(run_id, "context_done", "running", last_error="{}", complete=False)

            summary = repo.get_run_summary(deal_id="deal-1")
            self.assertIsNotNone(summary)
            assert summary is not None
            self.assertEqual(summary["run_id"], run_id)
            self.assertEqual(summary["current_stage"], "context_done")
            self.assertIn("action_step_status_counts", summary)


if __name__ == "__main__":
    unittest.main()
