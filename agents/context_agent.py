"""
Purpose:
Agent module `context_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
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
from context.models import DealContext, SignalContext

LOGGER = logging.getLogger(__name__)


def context_agent(
    raw_data: dict,
    signal_context: SignalContext,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> DealContext:
    prompt_text = render_prompt(
        "context_prompt.txt",
        prompt_contract={
            "workflow_goal": "Build normalized deal context for downstream strategy and action agents.",
            "stage_name": "context_agent",
            "policy_mode": "observe_only",
            "output_model": DealContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "context_agent",
        },
    )
    reasoning = "Built persona and objection context from deal snapshot and signal."
    confidence = 0.82 if signal_context.stalled else 0.7
    deterministic_payload = {
        "persona": raw_data.get("persona", "unknown"),
        "deal_stage": raw_data.get("deal_stage", "unknown"),
        "known_objections": list(raw_data.get("known_objections", [])),
        "recent_timeline": [raw_data.get("last_touch_summary", "")],
        "recommended_tone": "consultative" if signal_context.urgency != "low" else "neutral",
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(DealContext)
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    llm_enabled = runtime_config.enabled
    resolution = resolve_model_output(
        llm_enabled=llm_enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="context_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="context_agent",
        prompt_name="context_prompt.txt",
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
        stage_name="context_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"context_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    final_reasoning = str(payload["reasoning"])
    final_confidence = float(payload["confidence"])
    result = make_result(
        DealContext(
            persona=str(payload["persona"]),
            deal_stage=str(payload["deal_stage"]),
            known_objections=list(payload["known_objections"]),
            recent_timeline=list(payload["recent_timeline"]),
            recommended_tone=str(payload["recommended_tone"]),
            reasoning=final_reasoning,
            confidence=final_confidence,
        ),
        final_reasoning,
        final_confidence,
    )
    return result.payload
