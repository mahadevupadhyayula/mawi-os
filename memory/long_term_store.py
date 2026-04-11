"""
Purpose:
Memory module `long_term_store` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from typing import List

from memory.memory_models import OutcomeRecord, PersonaInsight


class LongTermMemory:
    def __init__(self) -> None:
        self.outcomes: List[OutcomeRecord] = []
        self.persona_insights: List[PersonaInsight] = []

    def add_outcome(self, record: OutcomeRecord) -> None:
        self.outcomes.append(record)

    def add_insight(self, record: PersonaInsight) -> None:
        self.persona_insights.append(record)

    def insights_for_persona(self, persona: str) -> List[PersonaInsight]:
        return [i for i in self.persona_insights if i.persona == persona]
