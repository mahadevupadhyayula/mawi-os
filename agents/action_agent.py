"""
Purpose:
Implements the Action Agent that generates executable outreach content from decision and deal context.

Technical Details:
Uses prompt templates plus lightweight persona-aware rules to build structured ActionContext output consumable by approval and execution layers.
"""

from __future__ import annotations

from uuid import uuid4

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import ActionPlanContext, ActionStep, DealContext, DecisionContext


def _memory_signal_strength(decision_context: DecisionContext) -> float:
    return max(0.0, min(0.15, float(decision_context.memory_confidence_impact or 0.0)))


def _memory_backed_cta(decision_context: DecisionContext) -> str:
    if not decision_context.memory_evidence_used:
        return "If helpful, I can send a 2-point plan and timeline options."
    if _memory_signal_strength(decision_context) >= 0.08:
        return "If you're open, I can send two concrete options and hold a 15-minute slot this week."
    return "If helpful, I can share two concrete next-step options tailored to your rollout timeline."


def _subject_and_preview(decision_context: DecisionContext) -> tuple[str, str]:
    if not decision_context.memory_evidence_used:
        return (
            "Quick follow-up on your rollout goals",
            "Sharing a concise ROI angle tailored to your current stage.",
        )
    if decision_context.strategy_type == "roi_framing":
        return (
            "Follow-up: ROI path based on similar deals",
            "Memory-backed ROI signal suggests a concise business-case follow-up.",
        )
    return (
        "Follow-up: reducing rollout risk",
        "Memory-backed signal suggests a low-risk next-step message for this stage.",
    )


def action_agent(
    decision_context: DecisionContext,
    deal_context: DealContext,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> ActionPlanContext:
    _ = render_prompt(
        "action_prompt.txt",
        prompt_contract={
            "workflow_goal": "Generate an ordered, approval-ready action plan from strategy and deal context.",
            "stage_name": "action_agent",
            "policy_mode": "policy_guided",
            "output_model": ActionPlanContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "action_agent",
        },
    )
    subject, preview = _subject_and_preview(decision_context)
    body = (
        f"Hi — following up with a short {decision_context.strategy_type.replace('_', ' ')} summary "
        f"for your {deal_context.deal_stage} stage. "
        f"{_memory_backed_cta(decision_context)}"
    )
    confidence = 0.74 if decision_context.strategy_type == "roi_framing" else 0.8
    reasoning = "Generated an ordered action plan with channel-specific steps."
    email_step = ActionStep(
        step_id=str(uuid4()),
        order=1,
        channel="email",
        action_type="send_email",
        subject=subject,
        preview=preview,
        body_draft=body,
        status="draft",
    )
    crm_preview = "Record ROI-focused follow-up in CRM timeline."
    crm_body = "Logged ROI framing follow-up and proposed timeline options."
    if decision_context.strategy_type != "roi_framing":
        crm_preview = "Record sequenced follow-up in CRM timeline."
        crm_body = "Logged sequenced follow-up and next-step timeline options."

    steps = [
        email_step,
        ActionStep(
            step_id=str(uuid4()),
            order=2,
            channel="crm",
            action_type="update_crm",
            preview=crm_preview,
            body_draft=crm_body,
            status="draft",
        ),
    ]
    result = make_result(
        ActionPlanContext(
            plan_id=str(uuid4()),
            steps=steps,
            status="draft",
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
