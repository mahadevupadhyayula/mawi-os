from __future__ import annotations

from context.schemas import ContextEnvelope, OutcomeSignal


def generate_insight(envelope: ContextEnvelope, outcome: OutcomeSignal) -> str:
    strategy = envelope.decision_context.current.structured.get("strategy_type", "unknown") if envelope.decision_context.current else "unknown"
    if outcome.replied:
        return f"{strategy} improved reply likelihood for this persona."
    return f"{strategy} did not convert; test alternative framing next cycle."
