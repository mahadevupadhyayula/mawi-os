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
from typing import Any, Mapping

from workflows.registry import DEFAULT_WORKFLOW_NAME

PROMPT_DIR = Path(__file__).parent / "prompts"
REQUIRED_PROMPT_CONTRACT_KEYS = (
    "workflow_goal",
    "stage_name",
    "policy_mode",
    "expected_output_schema",
)


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _normalize_contract(prompt_contract: Mapping[str, Any] | None) -> dict[str, str]:
    contract = dict(prompt_contract or {})
    contract.setdefault("workflow_id", DEFAULT_WORKFLOW_NAME)
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
    template = Template(load_prompt(name))
    rendered_body = template.safe_substitute(**{**contract, **kwargs})
    return f"{_contract_header(contract)}\n\n{rendered_body}"
