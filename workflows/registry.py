"""
Purpose:
Workflow module `registry` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations

from workflows.deal_followup_workflow import WORKFLOW_NAME, WORKFLOW_STEPS


WORKFLOW_REGISTRY = {WORKFLOW_NAME: WORKFLOW_STEPS}


def get_workflow_steps(name: str) -> list[str]:
    if name not in WORKFLOW_REGISTRY:
        raise ValueError(f"Unknown workflow: {name}")
    return WORKFLOW_REGISTRY[name]
