"""
Purpose:
Agent module `prompt_templates` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
import re
from string import Template
from threading import Lock
from typing import Any, Mapping

from context.models import (
    CONTEXT_SCHEMA_VERSION,
    ActionPlanContext,
    DealContext,
    DecisionContext,
    ExecutionContext,
    OutcomeContext,
    SignalContext,
)
from workflows.registry import DEFAULT_WORKFLOW_NAME, is_known_workflow

PROMPT_DIR = Path(__file__).parent / "prompts"
COMMON_PROMPT_PROFILE = "common"
PROMPT_MANIFEST_PATH = PROMPT_DIR / "manifest.json"
REQUIRED_PROMPT_CONTRACT_KEYS = (
    "workflow_goal",
    "stage_name",
    "policy_mode",
)
PROMPT_SCHEMA_VERSION = "v1"
SCHEMA_COMPATIBILITY_MATRIX: dict[str, set[str]] = {
    "v1": {"v1"},
}
PROMPT_OUTPUT_MODELS: dict[str, type] = {
    "signal_prompt.txt": SignalContext,
    "context_prompt.txt": DealContext,
    "strategist_prompt.txt": DecisionContext,
    "action_prompt.txt": ActionPlanContext,
    "execution_prompt.txt": ExecutionContext,
    "evaluator_prompt.txt": OutcomeContext,
}

_PROMPT_FALLBACK_TELEMETRY: dict[str, int] = {}
_PROMPT_TELEMETRY_LOCK = Lock()


def _record_prompt_fallback_event(*, workflow_id: str, prompt_name: str, reason: str) -> None:
    key = f"{workflow_id}:{prompt_name}:{reason}"
    with _PROMPT_TELEMETRY_LOCK:
        _PROMPT_FALLBACK_TELEMETRY[key] = _PROMPT_FALLBACK_TELEMETRY.get(key, 0) + 1


def get_prompt_fallback_telemetry() -> dict[str, int]:
    with _PROMPT_TELEMETRY_LOCK:
        return dict(_PROMPT_FALLBACK_TELEMETRY)


def load_prompt_manifest() -> dict[str, Any]:
    return json.loads(PROMPT_MANIFEST_PATH.read_text(encoding="utf-8"))


def _resolve_prompt_path(name: str, workflow_id: str) -> Path:
    workflow_prompt_path = PROMPT_DIR / workflow_id / name
    if workflow_prompt_path.exists():
        return workflow_prompt_path

    common_prompt_path = PROMPT_DIR / COMMON_PROMPT_PROFILE / name
    if common_prompt_path.exists():
        _record_prompt_fallback_event(workflow_id=workflow_id, prompt_name=name, reason="missing_workflow_prompt")
        return common_prompt_path

    raise FileNotFoundError(
        f"Unable to resolve prompt template '{name}' for workflow '{workflow_id}'. "
        f"Checked '{workflow_prompt_path}' then '{common_prompt_path}'."
    )


def load_prompt(name: str, workflow_id: str) -> str:
    path = _resolve_prompt_path(name, workflow_id)
    return path.read_text(encoding="utf-8")


def _required_json_fields(output_model: type) -> list[str]:
    if not is_dataclass(output_model):
        raise TypeError(f"output_model must be a dataclass type, got: {output_model!r}")
    return [field.name for field in fields(output_model) if field.name != "meta"]


def _extract_prompt_schema_version(template_text: str, name: str) -> str:
    match = re.search(r"^schema_version:\s*(\S+)\s*$", template_text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Prompt template '{name}' must declare a schema version (schema_version: vN).")
    return match.group(1)


def _resolve_output_model(name: str, contract: Mapping[str, Any]) -> type:
    output_model = contract.get("output_model") or PROMPT_OUTPUT_MODELS.get(name)
    if output_model is None:
        raise ValueError(f"Unable to resolve output model for prompt '{name}'.")
    return output_model


def _normalize_contract(name: str, prompt_contract: Mapping[str, Any] | None) -> dict[str, str]:
    contract = dict(prompt_contract or {})
    contract.setdefault("workflow_id", DEFAULT_WORKFLOW_NAME)
    workflow_id = str(contract["workflow_id"])
    if not is_known_workflow(workflow_id):
        known_workflows = ", ".join(sorted(load_prompt_manifest().get("profiles", {}).keys()))
        raise ValueError(
            f"Unknown workflow_id '{workflow_id}' in prompt contract. Supported prompt profiles: {known_workflows}"
        )

    missing = [key for key in REQUIRED_PROMPT_CONTRACT_KEYS if not contract.get(key)]
    if missing:
        missing_csv = ", ".join(sorted(missing))
        raise ValueError(f"prompt contract missing required keys: {missing_csv}")

    output_model = _resolve_output_model(name, contract)
    required_fields = _required_json_fields(output_model)

    normalized: dict[str, str] = {}
    for key, value in contract.items():
        normalized[key] = str(value)
    normalized["prompt_schema_version"] = PROMPT_SCHEMA_VERSION
    normalized["context_schema_version"] = CONTEXT_SCHEMA_VERSION
    normalized["output_model"] = output_model.__name__
    normalized["required_json_fields"] = json.dumps(required_fields)
    normalized["required_json_fields_csv"] = ", ".join(required_fields)
    return normalized


def _contract_header(contract: Mapping[str, str]) -> str:
    return "\n".join(
        [
            "PROMPT_CONTRACT",
            f"workflow_id: {contract['workflow_id']}",
            f"workflow_goal: {contract['workflow_goal']}",
            f"stage_name: {contract['stage_name']}",
            f"policy_mode: {contract['policy_mode']}",
            f"prompt_schema_version: {contract['prompt_schema_version']}",
            f"context_schema_version: {contract['context_schema_version']}",
            f"output_model: {contract['output_model']}",
            f"required_json_fields: {contract['required_json_fields']}",
        ]
    )


def render_prompt(name: str, *, prompt_contract: Mapping[str, Any] | None = None, **kwargs: str) -> str:
    contract = _normalize_contract(name, prompt_contract)
    prompt_text = load_prompt(name, contract["workflow_id"])
    declared_schema = _extract_prompt_schema_version(prompt_text, name)
    compatible_context_versions = SCHEMA_COMPATIBILITY_MATRIX.get(declared_schema, set())
    if CONTEXT_SCHEMA_VERSION not in compatible_context_versions:
        raise ValueError(
            f"Prompt schema '{declared_schema}' is not compatible with context schema '{CONTEXT_SCHEMA_VERSION}'."
        )
    template = Template(prompt_text)
    rendered_body = template.safe_substitute(**{**contract, **kwargs})
    return f"{_contract_header(contract)}\n\n{rendered_body}"
