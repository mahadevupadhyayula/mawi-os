"""
Purpose:
Implements the Signal Agent that interprets deal activity and identifies workflow-triggering events.

Technical Details:
Combines deterministic inactivity heuristics with typed SignalContext creation so downstream orchestration receives normalized event metadata.
"""

from __future__ import annotations

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import SignalContext


def signal_agent(raw_data: dict) -> SignalContext:
    _ = render_prompt("signal_prompt.txt")
    days = int(raw_data.get("days_since_reply", 0))
    stalled = days >= 5
    urgency = "high" if days >= 10 else "medium" if stalled else "low"
    reasoning = f"Deal has no reply for {days} days."
    confidence = 0.9 if stalled else 0.7
    result = make_result(
        SignalContext(
            stalled=stalled,
            days_since_reply=days,
            urgency=urgency,
            trigger_reason="no_reply_5_days" if stalled else "not_stalled",
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
