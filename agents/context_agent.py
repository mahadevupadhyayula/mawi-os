"""
Purpose:
Agent module `context_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

import json

from agents.contracts import make_result
from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from context.models import DealContext, SignalContext


def context_agent(
    raw_data: dict,
    signal_context: SignalContext,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> DealContext:
    _ = render_prompt(
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
    validation = validate_model_output_json(
        model_output=json.dumps(
            {
                "persona": raw_data.get("persona", "unknown"),
                "deal_stage": raw_data.get("deal_stage", "unknown"),
                "known_objections": list(raw_data.get("known_objections", [])),
                "recent_timeline": [raw_data.get("last_touch_summary", "")],
                "recommended_tone": "consultative" if signal_context.urgency != "low" else "neutral",
                "reasoning": reasoning,
                "confidence": confidence,
            }
        ),
        required_json_fields=required_json_fields(DealContext),
        stage_name="context_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"context_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    result = make_result(
        DealContext(
            persona=str(payload["persona"]),
            deal_stage=str(payload["deal_stage"]),
            known_objections=list(payload["known_objections"]),
            recent_timeline=list(payload["recent_timeline"]),
            recommended_tone=str(payload["recommended_tone"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
