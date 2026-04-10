from __future__ import annotations

from context.schemas import AgentSection, ContextEnvelope


SECTION_NAMES = {
    "signal_context",
    "deal_context",
    "decision_context",
    "action_context",
    "execution_context",
    "outcome_context",
}


def append_or_refine(envelope: ContextEnvelope, section_name: str, new_section: AgentSection) -> ContextEnvelope:
    if section_name not in SECTION_NAMES:
        raise ValueError(f"Unknown section: {section_name}")
    section_history = getattr(envelope, section_name)
    if section_history.current is not None:
        section_history.history.append(section_history.current)
    section_history.current = new_section
    return envelope
