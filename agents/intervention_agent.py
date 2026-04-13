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
from agents.inference import resolve_model_output
from agents.prompt_templates import (
    PromptLintError,
    attach_prompt_run_metadata,
    render_prompt,
    required_json_fields,
    validate_model_output_json,
)
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
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    resolution = resolve_model_output(
        llm_enabled=runtime_config.enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="intervention_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        max_retries=runtime_config.max_retries,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="intervention_agent",
        prompt_name="intervention_prompt.txt",
        llm_enabled=resolution.llm_enabled,
        provider=resolution.provider,
        model=resolution.model,
        llm_latency_ms=resolution.llm_latency_ms,
        token_usage=resolution.token_usage,
        fallback_reason=resolution.fallback_reason,
    )
    validation = validate_model_output_json(
        model_output=resolution.model_output,
        required_json_fields=required_fields,
        stage_name="intervention_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"intervention_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    final_reasoning = str(payload["reasoning"])
    final_confidence = float(payload["confidence"])

    result = make_result(
        InterventionDecisionContext(
            result=str(payload["result"]),
            reason=str(payload["reason"]),
            reasoning=final_reasoning,
            confidence=final_confidence,
        ),
        final_reasoning,
        final_confidence,
    )
    return result.payload
