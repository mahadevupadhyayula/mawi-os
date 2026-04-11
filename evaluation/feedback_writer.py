from __future__ import annotations

from memory.long_term_store import LongTermMemory
from memory.memory_models import PersonaInsight


def write_persona_feedback(memory: LongTermMemory, persona: str, insight: str, success_rate_hint: float) -> None:
    memory.add_insight(PersonaInsight(persona=persona, insight=insight, success_rate_hint=success_rate_hint))
