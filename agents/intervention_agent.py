"""
Purpose:
Implements the Intervention Agent that determines whether a deal needs intervention-only handling.

Technical Details:
Uses deterministic strategy-only heuristics (no execution/tool calls) and prompt contracts to return a typed InterventionDecisionContext payload.
"""

from __future__ import annotations

import json

from agents.contracts import make_result
from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from context.models import DealContext, InterventionDecisionContext, SignalContext



def intervention_agent(
    signal_context: SignalContext,
    deal_context: DealContext,
    *,
    workflow_id: str = "deal_intervention_workflow",
    run_id: str | None = None,
) -> InterventionDecisionContext:
    _ = render_prompt(
        "intervention_prompt.txt",
        prompt_contract={
            "workflow_goal": "Determine intervention strategy without triggering execution actions.",
            "stage_name": "intervention_agent",
            "policy_mode": "strategy_only",
            "output_model": InterventionDecisionContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "intervention_agent",
        },
    )

    elevated_risk = signal_context.urgency == "high" or any(
        token in " ".join(deal_context.known_objections).lower() for token in ("security", "legal", "risk")
    )

    if elevated_risk:
        result_label = "intervene"
        reason = "High urgency or risk objection detected; intervention strategy should be prioritized."
        confidence = 0.86
    elif signal_context.stalled:
        result_label = "monitor"
        reason = "Deal is stalled but risk signals are limited; monitor and reassess before intervention."
        confidence = 0.74
    else:
        result_label = "hold"
        reason = "No stall or risk signal requiring intervention at this time."
        confidence = 0.69

    reasoning = (
        f"Intervention decision '{result_label}' selected from urgency={signal_context.urgency}, "
        f"stalled={signal_context.stalled}, objections={deal_context.known_objections}."
    )
    validation = validate_model_output_json(
        model_output=json.dumps(
            {
                "result": result_label,
                "reason": reason,
                "reasoning": reasoning,
                "confidence": confidence,
            }
        ),
        required_json_fields=required_json_fields(InterventionDecisionContext),
        stage_name="intervention_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"intervention_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)

    result = make_result(
        InterventionDecisionContext(
            result=str(payload["result"]),
            reason=str(payload["reason"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
