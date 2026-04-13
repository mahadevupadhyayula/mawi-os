"""
Purpose:
Implements the Intervention Agent that determines whether a deal needs intervention-only handling.

Technical Details:
Uses deterministic strategy-only heuristics (no execution/tool calls) and prompt contracts to return a typed InterventionDecisionContext payload.
"""

from __future__ import annotations

import json
import logging

from agents.contracts import make_result
from agents.llm_client import LLMRequest, generate_json
from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from agents.runtime_config import load_runtime_llm_config
from context.models import DealContext, InterventionDecisionContext, SignalContext

LOGGER = logging.getLogger(__name__)


def intervention_agent(
    signal_context: SignalContext,
    deal_context: DealContext,
    *,
    workflow_id: str = "deal_intervention_workflow",
    run_id: str | None = None,
) -> InterventionDecisionContext:
    prompt_text = render_prompt(
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
    deterministic_payload = {
        "result": result_label,
        "reason": reason,
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(InterventionDecisionContext)
    model_output = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    if runtime_config.enabled:
        llm_result = generate_json(
            LLMRequest(
                prompt=prompt_text,
                required_fields=required_fields,
                model=runtime_config.openai_model,
                timeout_sec=runtime_config.timeout_sec,
            )
        )
        if llm_result.error:
            LOGGER.warning("intervention_agent llm fallback: %s", llm_result.error)
        elif llm_result.payload is None:
            LOGGER.warning("intervention_agent llm fallback: empty payload")
        else:
            llm_validation = validate_model_output_json(
                model_output=json.dumps(llm_result.payload),
                required_json_fields=required_fields,
                stage_name="intervention_agent",
            )
            if llm_validation["ok"]:
                model_output = json.dumps(llm_result.payload)
            else:
                LOGGER.warning("intervention_agent llm validation fallback: %s", llm_validation["errors"])
    validation = validate_model_output_json(
        model_output=model_output,
        required_json_fields=required_fields,
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
