from __future__ import annotations

import json
import unittest
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from agents.prompt_templates import PROMPT_OUTPUT_MODELS, load_prompt, render_prompt, required_json_fields, validate_model_output_json
from workflows.registry import WORKFLOW_REGISTRY

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "prompts"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_type(value: Any, expected_type: Any) -> bool:
    origin = get_origin(expected_type)
    if origin is None:
        if expected_type is Any:
            return True
        if expected_type is type(None):
            return value is None
        if isinstance(expected_type, type) and is_dataclass(expected_type):
            if not isinstance(value, dict):
                return False
            nested_hints = get_type_hints(expected_type)
            for nested_field in fields(expected_type):
                nested_expected = nested_hints.get(nested_field.name, nested_field.type)
                if nested_field.name not in value:
                    return False
                if not _validate_type(value[nested_field.name], nested_expected):
                    return False
            return True
        return isinstance(value, expected_type)

    if origin is list:
        (inner_type,) = get_args(expected_type)
        return isinstance(value, list) and all(_validate_type(item, inner_type) for item in value)

    if origin is dict:
        key_type, value_type = get_args(expected_type)
        return isinstance(value, dict) and all(
            _validate_type(key, key_type) and _validate_type(item, value_type) for key, item in value.items()
        )

    if origin is tuple:
        inner = get_args(expected_type)
        return isinstance(value, tuple) and len(value) == len(inner) and all(
            _validate_type(item, item_type) for item, item_type in zip(value, inner)
        )

    if str(origin).endswith("Literal"):
        return value in set(get_args(expected_type))

    if origin is not None and str(origin).endswith("Union"):
        return any(_validate_type(value, opt) for opt in get_args(expected_type))

    return True


def _assert_dataclass_shape(payload: dict[str, Any], model_cls: type) -> None:
    assert is_dataclass(model_cls), f"Expected dataclass model, got {model_cls!r}"
    type_hints = get_type_hints(model_cls)
    for field in fields(model_cls):
        if field.name == "meta":
            continue
        expected_type = type_hints.get(field.name, field.type)
        assert field.name in payload, f"Missing required field: {field.name}"
        assert _validate_type(payload[field.name], expected_type), (
            f"Invalid type for field '{field.name}': expected {expected_type}, got {type(payload[field.name])}"
        )


class TestPromptSimulationRegression(unittest.TestCase):
    def test_trigger_fixture_datasets_cover_workflow_scenarios(self) -> None:
        scenarios = _read_json(FIXTURES_DIR / "workflow_trigger_scenarios.json")
        self.assertGreaterEqual(len(scenarios), 3)

        for scenario in scenarios:
            raw_data = scenario["raw_data"]
            expected = scenario["expected"]
            for workflow_id, workflow_meta in WORKFLOW_REGISTRY.items():
                self.assertEqual(
                    workflow_meta.trigger(raw_data),
                    expected[workflow_id],
                    msg=f"Scenario '{scenario['scenario']}' mismatch for workflow '{workflow_id}'",
                )

    def test_rendered_prompt_snapshots_match_regression_baseline(self) -> None:
        render_scenarios = _read_json(FIXTURES_DIR / "prompt_render_scenarios.json")
        for scenario in render_scenarios:
            rendered = render_prompt(
                scenario["template"],
                prompt_contract=scenario["prompt_contract"],
            )
            snapshot_path = SNAPSHOT_DIR / scenario["snapshot"]
            expected = snapshot_path.read_text(encoding="utf-8")
            self.assertEqual(rendered, expected, msg=f"Snapshot drift for '{scenario['id']}'")

    def test_prompt_output_samples_are_schema_valid(self) -> None:
        samples = _read_json(FIXTURES_DIR / "prompt_output_samples.json")
        for template_name, output_model in PROMPT_OUTPUT_MODELS.items():
            with self.subTest(template=template_name):
                self.assertIn(template_name, samples)
                payload = samples[template_name]
                self.assertIsInstance(payload, dict)
                _assert_dataclass_shape(payload, output_model)
                validation = validate_model_output_json(
                    model_output=json.dumps(payload),
                    required_json_fields=required_json_fields(output_model),
                    stage_name=template_name.replace("_prompt.txt", ""),
                )
                self.assertTrue(validation["ok"])
                self.assertEqual(validation["errors"], [])

    def test_prompt_output_validation_emits_structured_errors_for_regression_audit(self) -> None:
        invalid_payload = {"reasoning": "ok", "confidence": -0.2}
        validation = validate_model_output_json(
            model_output=json.dumps(invalid_payload),
            required_json_fields=required_json_fields(PROMPT_OUTPUT_MODELS["signal_prompt.txt"]),
            stage_name="signal_agent",
        )
        self.assertFalse(validation["ok"])
        self.assertGreaterEqual(len(validation["errors"]), 2)
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("missing_required_fields", codes)
        self.assertIn("invalid_confidence_range", codes)

    def test_missing_workflow_prompt_falls_back_to_common_profile(self) -> None:
        fallback_body = load_prompt("context_prompt.txt", "new_deal_outreach_workflow")
        common_body = load_prompt("context_prompt.txt", "common")
        self.assertEqual(fallback_body, common_body)


if __name__ == "__main__":
    unittest.main()
