"""
Purpose:
Workflow module `registry` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agents.prompt_blocks import block_pack_for_workflow_type, merge_prompt_blocks

from workflows.crm_sync_workflow import (
    WORKFLOW_NAME as CRM_SYNC_WORKFLOW_NAME,
    WORKFLOW_STEPS as CRM_SYNC_WORKFLOW_STEPS,
)
from workflows.deal_followup_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.deal_intervention_workflow import (
    WORKFLOW_NAME as DEAL_INTERVENTION_WORKFLOW_NAME,
    WORKFLOW_STEPS as DEAL_INTERVENTION_WORKFLOW_STEPS,
)
from workflows.new_deal_outreach_workflow import (
    WORKFLOW_NAME as NEW_DEAL_WORKFLOW_NAME,
    WORKFLOW_STEPS as NEW_DEAL_WORKFLOW_STEPS,
)
from workflows.triggers import (
    should_trigger_crm_sync,
    should_trigger_deal_followup,
    should_trigger_deal_intervention,
    should_trigger_new_deal_outreach,
)


@dataclass(frozen=True)
class WorkflowMetadata:
    workflow_id: str
    steps: list[str]
    trigger: Callable[[dict[str, Any]], bool]
    config: dict[str, Any] = field(default_factory=dict)


DEFAULT_WORKFLOW_NAME = WORKFLOW_NAME
WORKFLOW_REGISTRY: dict[str, WorkflowMetadata] = {

    CRM_SYNC_WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=CRM_SYNC_WORKFLOW_NAME,
        steps=CRM_SYNC_WORKFLOW_STEPS,
        trigger=should_trigger_crm_sync,
        config={
            "release_version": "2026.04.1",
            "max_risk_tier_by_phase": {
                "default": "medium",
                "autonomous": "medium",
                "human_review": "medium",
            },
            "requires_explicit_or_post_action_event": True,
        },
    ),
    WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=WORKFLOW_NAME,
        steps=WORKFLOW_STEPS,
        trigger=should_trigger_deal_followup,
        config={
            "release_version": "2026.04.1",
            "max_risk_tier_by_phase": {
                "default": "high",
                "autonomous": "medium",
                "human_review": "high",
            }
        },
    ),
    NEW_DEAL_WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=NEW_DEAL_WORKFLOW_NAME,
        steps=NEW_DEAL_WORKFLOW_STEPS,
        trigger=should_trigger_new_deal_outreach,
        config={
            "release_version": "2026.04.1",
            "max_risk_tier_by_phase": {
                "default": "medium",
                "autonomous": "low",
                "human_review": "medium",
            }
        },
    ),
    DEAL_INTERVENTION_WORKFLOW_NAME: WorkflowMetadata(
        workflow_id=DEAL_INTERVENTION_WORKFLOW_NAME,
        steps=DEAL_INTERVENTION_WORKFLOW_STEPS,
        trigger=should_trigger_deal_intervention,
        config={
            "release_version": "2026.04.1",
            "max_risk_tier_by_phase": {
                "default": "critical",
                "autonomous": "medium",
                "human_review": "critical",
            },
        },
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


def get_workflow_release_version(name: str | None = None) -> str:
    workflow = get_workflow(name)
    return str(workflow.config.get("release_version", "unversioned"))


def register_generated_workflow(
    *,
    workflow_id: str,
    workflow_type: str,
    steps: list[str] | None = None,
    trigger: Callable[[dict[str, Any]], bool] | None = None,
    release_version: str = "generated",
    block_overrides: dict[str, str] | None = None,
    example_overrides: tuple[str, ...] | None = None,
) -> WorkflowMetadata:
    pack = block_pack_for_workflow_type(workflow_type)
    assembled_blocks = merge_prompt_blocks(
        default_blocks=pack.blocks,
        overrides=block_overrides,
        extra_examples=example_overrides,
    )
    metadata = WorkflowMetadata(
        workflow_id=workflow_id,
        steps=steps or list(WORKFLOW_STEPS),
        trigger=trigger or (lambda _raw: False),
        config={
            "release_version": release_version,
            "workflow_type": pack.workflow_type,
            "generated_prompt_blocks": [
                {"block_type": block.block_type, "content": block.content} for block in assembled_blocks
            ],
            "max_risk_tier_by_phase": {
                "default": "medium",
                "autonomous": "low",
                "human_review": "medium",
            },
        },
    )
    WORKFLOW_REGISTRY[workflow_id] = metadata
    return metadata


def get_generated_prompt_blocks(name: str) -> list[dict[str, str]] | None:
    workflow = WORKFLOW_REGISTRY.get(name)
    if workflow is None:
        return None
    blocks = workflow.config.get("generated_prompt_blocks")
    if not isinstance(blocks, list) or not blocks:
        return None
    return [dict(item) for item in blocks if isinstance(item, dict)]
