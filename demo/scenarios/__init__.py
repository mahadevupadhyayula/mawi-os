"""Loader for canonical MAWI demo scenario fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SCENARIO_DIRECTORY = Path(__file__).parent
SCENARIO_NAMES = (
    "stalled-deal-approval",
    "rejected-action",
    "llm-fallback",
)


def load_scenario(name: str) -> dict[str, Any]:
    """Load a named scenario and reject incomplete or non-canonical fixtures."""
    if name not in SCENARIO_NAMES:
        raise ValueError(f"Unknown demo scenario: {name}")

    payload = json.loads((SCENARIO_DIRECTORY / f"{name}.json").read_text(encoding="utf-8"))
    required = {"scenario_id", "workflow_id", "deal", "approval", "expected"}
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"Demo scenario '{name}' is missing fields: {', '.join(missing)}")
    if payload["scenario_id"] != name:
        raise ValueError(f"Demo scenario filename and scenario_id differ: {name}")
    if payload["workflow_id"] != "deal_followup_workflow":
        raise ValueError(f"Demo scenario '{name}' must use deal_followup_workflow")
    if not isinstance(payload["deal"], dict) or int(payload["deal"].get("days_since_reply", 0)) < 5:
        raise ValueError(f"Demo scenario '{name}' does not contain a stalled deal")
    return deepcopy(payload)


def load_scenarios() -> tuple[dict[str, Any], ...]:
    """Load all canonical scenarios in stable registry order."""
    return tuple(load_scenario(name) for name in SCENARIO_NAMES)
