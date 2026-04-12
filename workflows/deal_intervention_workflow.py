"""
Purpose:
Workflow module `deal_intervention_workflow` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations

WORKFLOW_NAME = "deal_intervention_workflow"
WORKFLOW_STEPS = [
    "signal_agent",
    "context_agent",
    "strategist_agent",
    "action_agent",
    "execution_agent",
    "evaluator_agent",
]
