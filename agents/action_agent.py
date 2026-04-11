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


def action_agent(decision_context: DecisionContext, deal_context: DealContext) -> ActionPlanContext:
    _ = render_prompt("action_prompt.txt")
    subject = "Quick follow-up on your rollout goals"
    preview = "Sharing a concise ROI angle tailored to your current stage."
    body = (
        f"Hi — following up with a short {decision_context.strategy_type.replace('_', ' ')} summary "
        f"for your {deal_context.deal_stage} stage. "
        "If helpful, I can send a 2-point plan and timeline options."
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
    steps = [email_step]
    if decision_context.strategy_type == "roi_framing":
        steps.append(
            ActionStep(
                step_id=str(uuid4()),
                order=2,
                channel="crm",
                action_type="update_crm",
                preview="Record ROI-focused follow-up in CRM timeline.",
                body_draft="Logged ROI framing follow-up and proposed timeline options.",
                status="draft",
            )
        )
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
