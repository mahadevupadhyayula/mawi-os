import unittest

from agents.prompt_templates import (
    PROMPT_OUTPUT_MODELS,
    PromptLintError,
    generate_prompt_health_report,
    get_prompt_fallback_telemetry,
    render_prompt,
    validate_prompt_health_report,
)
from context.models import DealContext


class TestPromptContracts(unittest.TestCase):
    def test_render_prompt_defaults_workflow_id(self) -> None:
        rendered = render_prompt(
            "signal_prompt.txt",
            prompt_contract={
                "workflow_goal": "Detect stalled deal activity.",
                "stage_name": "signal_agent",
                "policy_mode": "observe_only",
            },
        )

        self.assertIn("workflow_id: deal_followup_workflow", rendered)
        self.assertIn("stage_name: signal_agent", rendered)
        self.assertIn("prompt_schema_version: v1", rendered)
        self.assertIn("required_json_fields:", rendered)

    def test_render_prompt_raises_when_required_keys_missing(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            render_prompt(
                "signal_prompt.txt",
                prompt_contract={
                    "stage_name": "signal_agent",
                    "policy_mode": "observe_only",
                },
            )

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
            },
        )

        telemetry = get_prompt_fallback_telemetry()
        expected_key = "new_deal_outreach_workflow:context_prompt.txt:missing_workflow_prompt"
        self.assertGreaterEqual(telemetry.get(expected_key, 0), 1)

    def test_render_prompt_uses_active_dataclass_fields(self) -> None:
        rendered = render_prompt(
            "context_prompt.txt",
            prompt_contract={
                "workflow_goal": "Gather follow-up context.",
                "stage_name": "context_agent",
                "policy_mode": "observe_only",
                "output_model": DealContext,
            },
        )
        self.assertIn("output_model: DealContext", rendered)
        self.assertIn(
            "required_json_fields: [\"reasoning\", \"confidence\", \"persona\", \"deal_stage\", "
            "\"known_objections\", \"recent_timeline\", \"recommended_tone\"]",
            rendered,
        )
        self.assertIn(
            "Output Fields: Return JSON object with required fields: reasoning, confidence, persona, deal_stage, "
            "known_objections, recent_timeline, recommended_tone.",
            rendered,
        )

    def test_all_prompt_templates_match_model_declared_fields(self) -> None:
        for prompt_name, output_model in PROMPT_OUTPUT_MODELS.items():
            rendered = render_prompt(
                prompt_name,
                prompt_contract={
                    "workflow_goal": "Contract validation",
                    "stage_name": "contract_test",
                    "policy_mode": "observe_only",
                    "output_model": output_model,
                },
            )
            required_fields = [
                field.strip()
                for field in rendered.split("Return JSON object with required fields:", maxsplit=1)[1]
                .split(".", maxsplit=1)[0]
                .split(",")
            ]
            header_fields = rendered.split("required_json_fields: ", maxsplit=1)[1].split("\n", maxsplit=1)[0]
            for field in required_fields:
                self.assertIn(f'"{field}"', header_fields)

    def test_render_prompt_rejects_unused_render_kwargs(self) -> None:
        with self.assertRaises(PromptLintError) as ctx:
            render_prompt(
                "signal_prompt.txt",
                prompt_contract={
                    "workflow_goal": "Detect stalled deal activity.",
                    "stage_name": "signal_agent",
                    "policy_mode": "observe_only",
                },
                extra_placeholder="not-used",
            )

        self.assertIn("unused render kwargs", str(ctx.exception))

    def test_prompt_health_report_passes_for_all_workflow_agent_combinations(self) -> None:
        report = generate_prompt_health_report()
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreater(report["summary"]["total"], 0)
        validate_prompt_health_report(report)


if __name__ == "__main__":
    unittest.main()
