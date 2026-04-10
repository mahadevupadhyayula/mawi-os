from __future__ import annotations

from context.merge_rules import append_or_refine
from context.schemas import AgentSection, ContextEnvelope


def strategist_agent(envelope: ContextEnvelope) -> ContextEnvelope:
    signal = envelope.signal_context.current.structured if envelope.signal_context.current else {}
    deal = envelope.deal_context.current.structured if envelope.deal_context.current else {}
    strategy = "roi_framing" if "unclear ROI" in deal.get("open_objections", []) else "timeline_nudge"
    section = AgentSection(
        structured={
            "strategy_type": strategy,
            "goal": "get_reply",
            "risk_flags": ["message_fatigue"] if signal.get("no_reply_days", 0) > 10 else [],
            "success_hypothesis": "ROI framing improves reply probability for finance-conscious personas.",
        },
        reasoning="Strategy selected based on objections and inactivity length.",
        confidence=0.78,
    )
    envelope.meta.workflow_stage = "strategist_agent"
    return append_or_refine(envelope, "decision_context", section)
