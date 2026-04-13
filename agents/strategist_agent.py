"""
Purpose:
Implements the Strategist Agent that converts signal and deal context into a recommended strategy for next-best action.

Technical Details:
Renders strategist prompt templates, applies deterministic strategy selection logic for MVP behavior, and returns typed DecisionContext payloads via shared contracts.
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
from context.models import DealContext, DecisionContext, SignalContext

LOGGER = logging.getLogger(__name__)


def strategist_agent(
    signal_context: SignalContext,
    deal_context: DealContext,
    memory_evidence: list[dict] | None = None,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> DecisionContext:
    prompt_text = render_prompt(
        "strategist_prompt.txt",
        prompt_contract={
            "workflow_goal": "Select a next-best strategy that restarts stalled conversations.",
            "stage_name": "strategist_agent",
            "policy_mode": "policy_guided",
            "output_model": DecisionContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "strategist_agent",
        },
    )
    baseline_strategy = "roi_framing" if "budget timing" in deal_context.known_objections else "risk_reduction"
    evidence = [item for item in (memory_evidence or []) if isinstance(item, dict)]
    evidence_text = " ".join(item.get("snippet", "").lower() for item in evidence)

    raw_impact = round(sum(float(item.get("confidence_impact", 0.0)) for item in evidence), 3)
    # Guardrail: preserve the current no-memory confidence band while allowing bounded lift with evidence.
    memory_confidence_impact = max(0.0, min(raw_impact, 0.15))

    if not evidence:
        strategy_type = baseline_strategy
        confidence = 0.78
        memory_rationale = "No memory evidence available; used baseline strategist rules."
        reasoning = f"Selected {strategy_type} based on objections and urgency={signal_context.urgency}."
    else:
        if "roi" in evidence_text:
            strategy_type = "roi_framing"
        elif "risk" in evidence_text:
            strategy_type = "risk_reduction"
        else:
            strategy_type = baseline_strategy
        confidence = 0.78 + memory_confidence_impact
        memory_rationale = (
            f"Used {len(evidence)} memory evidence item(s) to bias deterministic strategy selection "
            f"and apply confidence impact +{memory_confidence_impact:.3f}."
        )
        reasoning = f"Selected {strategy_type} based on objections and urgency={signal_context.urgency}. {memory_rationale}"
    deterministic_payload = {
        "strategy_id": f"strat-{strategy_type}",
        "strategy_type": strategy_type,
        "message_goal": "restart_conversation",
        "fallback_strategy": "social_proof",
        "memory_evidence_used": evidence,
        "memory_confidence_impact": memory_confidence_impact,
        "memory_rationale": memory_rationale,
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(DecisionContext)
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    llm_enabled = runtime_config.enabled
    resolution = resolve_model_output(
        llm_enabled=llm_enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="strategist_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="strategist_agent",
        prompt_name="strategist_prompt.txt",
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
        stage_name="strategist_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"strategist_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    result = make_result(
        DecisionContext(
            strategy_id=str(payload["strategy_id"]),
            strategy_type=str(payload["strategy_type"]),
            message_goal=str(payload["message_goal"]),
            fallback_strategy=str(payload["fallback_strategy"]),
            memory_evidence_used=list(payload["memory_evidence_used"]),
            memory_confidence_impact=float(payload["memory_confidence_impact"]),
            memory_rationale=str(payload["memory_rationale"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
