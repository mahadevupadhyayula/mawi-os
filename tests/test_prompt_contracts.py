import unittest

from agents.prompt_templates import get_prompt_fallback_telemetry, render_prompt


class TestPromptContracts(unittest.TestCase):
    def test_render_prompt_defaults_workflow_id(self) -> None:
        rendered = render_prompt(
            "signal_prompt.txt",
            prompt_contract={
                "workflow_goal": "Detect stalled deal activity.",
                "stage_name": "signal_agent",
                "policy_mode": "observe_only",
                "expected_output_schema": "SignalContext(...)",
            },
        )

        self.assertIn("workflow_id: deal_followup_workflow", rendered)
        self.assertIn("stage_name: signal_agent", rendered)

    def test_render_prompt_raises_when_required_keys_missing(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            render_prompt(
                "signal_prompt.txt",
                prompt_contract={
                    "stage_name": "signal_agent",
                    "policy_mode": "observe_only",
                },
            )

        self.assertIn("expected_output_schema", str(ctx.exception))
        self.assertIn("workflow_goal", str(ctx.exception))

    def test_render_prompt_raises_for_unknown_workflow_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            render_prompt(
                "signal_prompt.txt",
                prompt_contract={
                    "workflow_id": "non_existent_workflow",
                    "workflow_goal": "Detect stalled deal activity.",
                    "stage_name": "signal_agent",
                    "policy_mode": "observe_only",
                    "expected_output_schema": "SignalContext(...)",
                },
            )

        self.assertIn("Unknown workflow_id", str(ctx.exception))
        self.assertIn("deal_followup_workflow", str(ctx.exception))

    def test_render_prompt_records_fallback_telemetry(self) -> None:
        render_prompt(
            "context_prompt.txt",
            prompt_contract={
                "workflow_id": "new_deal_outreach_workflow",
                "workflow_goal": "Gather follow-up context.",
                "stage_name": "context_agent",
                "policy_mode": "observe_only",
                "expected_output_schema": "DealContext(...)",
            },
        )

        telemetry = get_prompt_fallback_telemetry()
        expected_key = "new_deal_outreach_workflow:context_prompt.txt:missing_workflow_prompt"
        self.assertGreaterEqual(telemetry.get(expected_key, 0), 1)


if __name__ == "__main__":
    unittest.main()
