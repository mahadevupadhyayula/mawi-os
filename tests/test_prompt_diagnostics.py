import unittest

from agents.prompt_templates import get_prompt_diagnostics_report, render_prompt


class TestPromptDiagnostics(unittest.TestCase):
    def test_render_prompt_logs_profile_and_run_metadata(self) -> None:
        run_id = "test-run-diagnostics-1"
        _ = render_prompt(
            "signal_prompt.txt",
            prompt_contract={
                "workflow_id": "deal_followup_workflow",
                "workflow_goal": "Detect stalled deal activity.",
                "stage_name": "signal_agent",
                "policy_mode": "observe_only",
                "run_id": run_id,
                "agent_id": "signal_agent",
            },
        )
        report = get_prompt_diagnostics_report(limit=5)
        self.assertIn("summary", report)
        self.assertIn("performance", report)
        self.assertGreaterEqual(report["summary"]["total_prompt_runs"], 1)

    def test_schema_validation_errors_are_counted(self) -> None:
        with self.assertRaises(Exception):
            render_prompt(
                "signal_prompt.txt",
                prompt_contract={
                    "workflow_goal": "Detect stalled deal activity.",
                    "stage_name": "signal_agent",
                    "policy_mode": "observe_only",
                },
                extra_placeholder="unused",
            )
        report = get_prompt_diagnostics_report(limit=5)
        self.assertGreaterEqual(report["summary"]["schema_validation_errors"], 1)


if __name__ == "__main__":
    unittest.main()
