import unittest

from agents.prompt_templates import (
    PROMPT_OUTPUT_MODELS,
    PromptLintError,
    generate_prompt_health_report,
    get_prompt_fallback_telemetry,
    load_prompt_manifest,
    required_json_fields,
    render_prompt,
    validate_model_output_json,
    validate_prompt_health_report,
)
from context.models import DealContext
from workflows.registry import WORKFLOW_REGISTRY, register_generated_workflow


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
        self.assertIn("policy_instruction_version:", rendered)
        self.assertIn("strategy_instruction_version:", rendered)
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


    def test_register_generated_workflow_uses_block_pack_template(self) -> None:
        workflow_id = "generated_outreach_contract_test"
        try:
            register_generated_workflow(
                workflow_id=workflow_id,
                workflow_type="outreach",
                block_overrides={
                    "goal": "Assemble ${stage_name} output for generated outreach workflow.",
                },
                example_overrides=("Use one concrete CTA.",),
            )
            rendered = render_prompt(
                "action_prompt.txt",
                prompt_contract={
                    "workflow_id": workflow_id,
                    "workflow_goal": "Generated workflow run.",
                    "stage_name": "action_agent",
                    "policy_mode": "policy_guided",
                },
            )
            self.assertIn("workflow_id: generated_outreach_contract_test", rendered)
            self.assertIn("Assemble action_agent output for generated outreach workflow.", rendered)
            self.assertIn("Examples: Use as guidance only.", rendered)
        finally:
            WORKFLOW_REGISTRY.pop(workflow_id, None)


    def test_generated_workflow_default_block_packs_cover_common_types(self) -> None:
        for workflow_type in ("outreach", "intervention", "follow-up"):
            workflow_id = f"generated_{workflow_type.replace('-', '_')}_contract_test"
            try:
                register_generated_workflow(workflow_id=workflow_id, workflow_type=workflow_type)
                rendered = render_prompt(
                    "signal_prompt.txt",
                    prompt_contract={
                        "workflow_id": workflow_id,
                        "workflow_goal": "Generated workflow run.",
                        "stage_name": "signal_agent",
                        "policy_mode": "observe_only",
                    },
                )
                self.assertIn("Role: You are signal", rendered)
                self.assertIn("Output Fields: Return JSON object with required fields", rendered)
            finally:
                WORKFLOW_REGISTRY.pop(workflow_id, None)

    def test_register_generated_workflow_validates_required_block_schema(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            register_generated_workflow(
                workflow_id="generated_invalid_contract_test",
                workflow_type="intervention",
                block_overrides={"invalid": "bad override"},
            )

        self.assertIn("Unknown prompt block override keys", str(ctx.exception))

    def test_prompt_health_report_passes_for_all_workflow_agent_combinations(self) -> None:
        report = generate_prompt_health_report()
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreater(report["summary"]["total"], 0)
        validate_prompt_health_report(report)

    def test_prompt_manifest_registry_includes_governance_fields(self) -> None:
        manifest = load_prompt_manifest()
        self.assertIn("prompt_registry_index", manifest)
        self.assertGreater(len(manifest["prompt_registry_index"]), 0)
        first_entry = manifest["prompt_registry_index"][0]
        self.assertIn(first_entry["status"], {"draft", "active", "deprecated"})
        self.assertTrue(first_entry["owner"])
        self.assertTrue(first_entry["changelog"])

    def test_validate_model_output_json_returns_structured_error_for_missing_fields(self) -> None:
        report = validate_model_output_json(
            model_output='{"reasoning":"ok","confidence":0.8}',
            required_json_fields=required_json_fields(DealContext),
            stage_name="context_agent",
        )
        self.assertFalse(report["ok"])
        self.assertIsNone(report["payload"])
        self.assertEqual(report["errors"][0]["code"], "missing_required_fields")
        self.assertEqual(report["errors"][0]["stage_name"], "context_agent")
        self.assertIn("persona", report["errors"][0]["details"]["missing_fields"])

    def test_validate_model_output_json_rejects_out_of_range_confidence(self) -> None:
        report = validate_model_output_json(
            model_output='{"reasoning":"ok","confidence":1.2,"stalled":true,"days_since_reply":7,'
            '"urgency":"high","trigger_reason":"no_reply_5_days"}',
            required_json_fields=["reasoning", "confidence", "stalled", "days_since_reply", "urgency", "trigger_reason"],
            stage_name="signal_agent",
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "invalid_confidence_range")

    def test_validate_model_output_json_accepts_valid_payload(self) -> None:
        report = validate_model_output_json(
            model_output='{"reasoning":"ok","confidence":0.6,"stalled":false,"days_since_reply":1,'
            '"urgency":"low","trigger_reason":"not_stalled"}',
            required_json_fields=["reasoning", "confidence", "stalled", "days_since_reply", "urgency", "trigger_reason"],
            stage_name="signal_agent",
        )
        self.assertTrue(report["ok"])
        self.assertEqual(report["payload"]["confidence"], 0.6)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
