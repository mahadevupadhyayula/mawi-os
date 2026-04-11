"""
Purpose:
Agent module `context_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import DealContext, SignalContext


def context_agent(raw_data: dict, signal_context: SignalContext) -> DealContext:
    _ = render_prompt("context_prompt.txt")
    reasoning = "Built persona and objection context from deal snapshot and signal."
    confidence = 0.82 if signal_context.stalled else 0.7
    result = make_result(
        DealContext(
            persona=raw_data.get("persona", "unknown"),
            deal_stage=raw_data.get("deal_stage", "unknown"),
            known_objections=list(raw_data.get("known_objections", [])),
            recent_timeline=[raw_data.get("last_touch_summary", "")],
            recommended_tone="consultative" if signal_context.urgency != "low" else "neutral",
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
