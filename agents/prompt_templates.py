"""
Purpose:
Agent module `prompt_templates` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from threading import Lock
from typing import Any, Mapping

from workflows.registry import DEFAULT_WORKFLOW_NAME, is_known_workflow

PROMPT_DIR = Path(__file__).parent / "prompts"
COMMON_PROMPT_PROFILE = "common"
PROMPT_MANIFEST_PATH = PROMPT_DIR / "manifest.json"
REQUIRED_PROMPT_CONTRACT_KEYS = (
    "workflow_goal",
    "stage_name",
    "policy_mode",
    "expected_output_schema",
)

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


def _normalize_contract(prompt_contract: Mapping[str, Any] | None) -> dict[str, str]:
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

    normalized: dict[str, str] = {}
    for key, value in contract.items():
        if key == "expected_output_schema" and isinstance(value, (dict, list, tuple)):
            normalized[key] = json.dumps(value, sort_keys=True)
        else:
            normalized[key] = str(value)
    return normalized


def _contract_header(contract: Mapping[str, str]) -> str:
    return "\n".join(
        [
            "PROMPT_CONTRACT",
            f"workflow_id: {contract['workflow_id']}",
            f"workflow_goal: {contract['workflow_goal']}",
            f"stage_name: {contract['stage_name']}",
            f"policy_mode: {contract['policy_mode']}",
            f"expected_output_schema: {contract['expected_output_schema']}",
        ]
    )


def render_prompt(name: str, *, prompt_contract: Mapping[str, Any] | None = None, **kwargs: str) -> str:
    contract = _normalize_contract(prompt_contract)
    template = Template(load_prompt(name, contract["workflow_id"]))
    rendered_body = template.safe_substitute(**{**contract, **kwargs})
    return f"{_contract_header(contract)}\n\n{rendered_body}"
