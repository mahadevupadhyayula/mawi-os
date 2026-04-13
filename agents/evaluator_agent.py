"""
Purpose:
Agent module `evaluator_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

from agents.contracts import ExecutionOutcome, make_result
import json

from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from context.models import ExecutionContext, OutcomeContext
from evaluation.outcome_analyzer import classify_outcome_detailed


def evaluator_agent(
    execution_context: ExecutionContext,
    outcome: ExecutionOutcome,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> OutcomeContext:
    _ = render_prompt(
        "evaluator_prompt.txt",
        prompt_contract={
            "workflow_goal": "Evaluate execution outcomes and produce reusable learning signals.",
            "stage_name": "evaluator_agent",
            "policy_mode": "observe_only",
            "output_model": OutcomeContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "evaluator_agent",
        },
    )
    outcome_label = classify_outcome_detailed(outcome, execution_success=execution_context.status == "executed")
    if outcome_label == "delivery_failure":
        label = "negative"
        insight = "Execution reliability issues reduced follow-up quality."
        adjustment = "Improve tool retry and fallback policies."
        confidence = 0.7
    elif outcome_label == "positive":
        label = "positive"
        insight = "ROI framing improved reply likelihood for this persona."
        adjustment = "Prioritize ROI framing for similar stalled proposal-stage deals."
        confidence = 0.85
    elif outcome_label == "delayed_positive":
        label = "positive"
        insight = "Late interest signal observed; sequencing likely worked with slower buyer timing."
        adjustment = "Retain sequence structure and extend follow-up window before switching tactics."
        confidence = 0.74
    else:
        label = "neutral"
        insight = "Action executed but no reply yet; timing or message angle may need refinement."
        adjustment = "Test shorter CTA and add concrete next-step options."
        confidence = 0.65

    reasoning = "Compared execution result with observed outcome and generated learning signal."
    validation = validate_model_output_json(
        model_output=json.dumps(
            {
                "outcome_label": label,
                "insight": insight,
                "recommended_adjustment": adjustment,
                "reasoning": reasoning,
                "confidence": confidence,
            }
        ),
        required_json_fields=required_json_fields(OutcomeContext),
        stage_name="evaluator_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"evaluator_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    result = make_result(
        OutcomeContext(
            outcome_label=str(payload["outcome_label"]),
            insight=str(payload["insight"]),
            recommended_adjustment=str(payload["recommended_adjustment"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
