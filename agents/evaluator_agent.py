"""
Purpose:
Agent module `evaluator_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

from agents.contracts import ExecutionOutcome, make_result
from agents.prompt_templates import render_prompt
from context.models import ExecutionContext, OutcomeContext


def evaluator_agent(execution_context: ExecutionContext, outcome: ExecutionOutcome) -> OutcomeContext:
    _ = render_prompt(
        "evaluator_prompt.txt",
        prompt_contract={
            "workflow_goal": "Evaluate execution outcomes and produce reusable learning signals.",
            "stage_name": "evaluator_agent",
            "policy_mode": "observe_only",
            "output_model": OutcomeContext,
        },
    )
    if execution_context.status != "executed":
        label = "negative"
        insight = "Execution reliability issues reduced follow-up quality."
        adjustment = "Improve tool retry and fallback policies."
        confidence = 0.7
    elif outcome.reply_received:
        label = "positive"
        insight = "ROI framing improved reply likelihood for this persona."
        adjustment = "Prioritize ROI framing for similar stalled proposal-stage deals."
        confidence = 0.85
    else:
        label = "neutral"
        insight = "Action executed but no reply yet; timing or message angle may need refinement."
        adjustment = "Test shorter CTA and add concrete next-step options."
        confidence = 0.65

    reasoning = "Compared execution result with observed outcome and generated learning signal."
    result = make_result(
        OutcomeContext(
            outcome_label=label,
            insight=insight,
            recommended_adjustment=adjustment,
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
