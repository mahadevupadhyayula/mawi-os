from __future__ import annotations

from context.merge_rules import append_or_refine
from context.schemas import AgentSection, ContextEnvelope


def context_agent(envelope: ContextEnvelope) -> ContextEnvelope:
    raw = envelope.raw_data
    signal = envelope.signal_context.current.structured if envelope.signal_context.current else {}
    section = AgentSection(
        structured={
            "account_profile": raw.get("account_profile", "mid-market saas"),
            "persona": raw.get("persona", "VP Sales"),
            "deal_stage": raw.get("deal_stage", "proposal"),
            "open_objections": raw.get("open_objections", ["unclear ROI"]),
            "historical_interactions_summary": raw.get("interaction_summary", "2 demos, 1 proposal"),
            "recommended_tone_constraints": ["concise", "value-driven"],
            "priority_score": signal.get("priority_score", 0.5),
        },
        reasoning="Context enriched from raw CRM fields and activity summaries.",
        confidence=0.85,
    )
    envelope.meta.workflow_stage = "context_agent"
    return append_or_refine(envelope, "deal_context", section)
