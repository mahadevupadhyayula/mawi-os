from __future__ import annotations

from context.merge_rules import append_or_refine
from context.schemas import AgentSection, ContextEnvelope


def signal_agent(envelope: ContextEnvelope) -> ContextEnvelope:
    raw = envelope.raw_data
    no_reply_days = int(raw.get("no_reply_days", 0))
    stalled = no_reply_days >= 5
    priority = min(1.0, 0.4 + (no_reply_days / 20.0)) if stalled else 0.2
    section = AgentSection(
        structured={
            "stalled_detected": stalled,
            "no_reply_days": no_reply_days,
            "stall_reason_candidates": ["timing", "budget", "low urgency"],
            "priority_score": round(priority, 2),
        },
        reasoning="Deal is considered stalled when no reply is at least 5 days.",
        confidence=0.9 if stalled else 0.6,
    )
    envelope.meta.workflow_stage = "signal_agent"
    return append_or_refine(envelope, "signal_context", section)
