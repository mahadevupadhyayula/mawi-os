from __future__ import annotations

from context.merge_rules import append_or_refine
from context.schemas import AgentSection, ContextEnvelope, OutcomeSignal
from evaluation.insight_generator import generate_insight


def evaluator_agent(envelope: ContextEnvelope, outcome: OutcomeSignal) -> ContextEnvelope:
    execution = envelope.execution_context.current.structured if envelope.execution_context.current else {}
    outcome_label = "success" if outcome.replied or outcome.meeting_booked else "failure"
    insight = generate_insight(envelope, outcome)

    section = AgentSection(
        structured={
            "outcome_label": outcome_label,
            "replied": outcome.replied,
            "meeting_booked": outcome.meeting_booked,
            "response_latency_days": outcome.response_latency_days,
            "insight": insight,
            "action_id": execution.get("action_id"),
        },
        reasoning="Compared execution records with observed response outcome.",
        confidence=0.84,
    )
    envelope.meta.workflow_stage = "evaluator_agent"
    return append_or_refine(envelope, "outcome_context", section)
