import unittest

from agents.prompt_templates import render_prompt


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


if __name__ == "__main__":
    unittest.main()
