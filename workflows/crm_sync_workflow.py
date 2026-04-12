"""
Purpose:
Workflow module `crm_sync_workflow` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations

WORKFLOW_NAME = "crm_sync_workflow"
WORKFLOW_STEPS = [
    "signal_agent",
    "context_agent",
    "crm_agent",
    "execution_agent",
    "evaluator_agent",
]
