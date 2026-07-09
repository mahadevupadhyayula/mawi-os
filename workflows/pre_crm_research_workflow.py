"""
Purpose:
Workflow contract for the MAWI Pre-CRM Research Agent.

This workflow qualifies companies before CRM entry by separating evidence
collection, ICP scoring, human review, CRM payload creation, outreach task
creation, and learning updates.

Implementation status: Partial / workflow contract.
The workflow is registered so it can be progressively connected to concrete
agents, tools, persistence, and API routes.
"""

from __future__ import annotations

WORKFLOW_NAME = "pre_crm_research_workflow"

WORKFLOW_GOAL = (
    "Research, score, and qualify leads before CRM entry so GTM teams can "
    "avoid CRM clutter, prioritize better-fit accounts, and generate "
    "approval-ready outreach tasks."
)

WORKFLOW_STEPS = [
    "icp_context_agent",
    "company_signal_research_agent",
    "icp_evaluation_agent",
    "human_review_gate_agent",
    "crm_payload_agent",
    "outreach_task_agent",
    "learning_update_agent",
]

STATE_SECTIONS = [
    "company_input",
    "icp_context",
    "company_research_notes",
    "company_signal_context",
    "pre_crm_evaluation",
    "human_review",
    "crm_payload",
    "outreach_task",
    "learning_update",
    "state_log",
]

SCORING_WEIGHTS = {
    "firmographic_icp_fit": 20,
    "sales_motion_fit": 20,
    "gtm_pain_intensity": 25,
    "tool_data_readiness": 15,
    "urgency_trigger_strength": 10,
    "buyer_accessibility": 10,
}

DECISION_THRESHOLDS = {
    "strong_fit": "80-100",
    "good_fit": "65-79",
    "unclear_fit": "50-64",
    "poor_fit": "below 50",
}

ALLOWED_FINAL_ACTIONS = [
    "add_to_crm",
    "research_more",
    "add_to_watchlist",
    "manual_review",
    "reject",
]

ALLOWED_HUMAN_DECISIONS = [
    "approve_add_to_crm",
    "reject",
    "research_more",
    "add_to_watchlist",
    "manual_review_later",
]

IMPLEMENTATION_STATUS = "partial"
