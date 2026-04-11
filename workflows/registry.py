"""
Purpose:
Workflow module `registry` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from workflows.deal_followup_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.new_deal_outreach_workflow import (
    WORKFLOW_NAME as NEW_DEAL_WORKFLOW_NAME,
    WORKFLOW_STEPS as NEW_DEAL_WORKFLOW_STEPS,
)
from workflows.triggers import should_trigger_deal_followup, should_trigger_new_deal_outreach


@dataclass(frozen=True)
class WorkflowMetadata:
    workflow_id: str
    steps: list[str]
    trigger: Callable[[dict[str, Any]], bool]
    config: dict[str, Any] = field(default_factory=dict)


DEFAULT_WORKFLOW_NAME = WORKFLOW_NAME
WORKFLOW_REGISTRY: dict[str, WorkflowMetadata] = {
    WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=WORKFLOW_NAME,
        steps=WORKFLOW_STEPS,
        trigger=should_trigger_deal_followup,
    ),
    NEW_DEAL_WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=NEW_DEAL_WORKFLOW_NAME,
        steps=NEW_DEAL_WORKFLOW_STEPS,
        trigger=should_trigger_new_deal_outreach,
    ),
}


def get_workflow(name: str | None = None) -> WorkflowMetadata:
    workflow_name = name or DEFAULT_WORKFLOW_NAME
    if workflow_name not in WORKFLOW_REGISTRY:
        raise ValueError(f"Unknown workflow: {workflow_name}")
    return WORKFLOW_REGISTRY[workflow_name]


def is_known_workflow(name: str) -> bool:
    return name in WORKFLOW_REGISTRY


def get_registered_workflow_names() -> list[str]:
    return sorted(WORKFLOW_REGISTRY.keys())
