from __future__ import annotations

from dataclasses import asdict
from typing import Any

from context.models import ContextEnvelope


ALLOWED_SECTION_WRITES = {
    "signal_agent": "signal_context",
    "context_agent": "deal_context",
    "strategist_agent": "decision_context",
    "action_agent": "action_context",
    "execution_agent": "execution_context",
    "evaluator_agent": "outcome_context",
}


class ContextMutationError(Exception):
    pass


def append_or_refine_section(envelope: ContextEnvelope, *, agent_name: str, section_value: Any) -> ContextEnvelope:
    section_name = ALLOWED_SECTION_WRITES.get(agent_name)
    if section_name is None:
        raise ContextMutationError(f"Unknown agent {agent_name}")

    current = getattr(envelope, section_name)
    if current is not None:
        section_value.meta.version = current.meta.version + 1
        section_value.meta.parent_version = current.meta.version
        section_value.meta.created_at = current.meta.created_at
    section_value.meta.source_agent = agent_name
    setattr(envelope, section_name, section_value)
    envelope.history.append({"agent": agent_name, "section": section_name, "value": asdict(section_value)})
    return envelope


def set_stage(envelope: ContextEnvelope, stage: str) -> ContextEnvelope:
    envelope.meta.workflow_stage = stage
    return envelope
