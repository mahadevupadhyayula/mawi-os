from __future__ import annotations

from memory.repository import ListRepository


class LongTermMemory:
    def __init__(self) -> None:
        self.actions = ListRepository()
        self.outcomes = ListRepository()
        self.persona_insights = ListRepository()

    def record_action(self, record: dict) -> None:
        self.actions.append(record)

    def record_outcome(self, record: dict) -> None:
        self.outcomes.append(record)

    def record_persona_insight(self, insight: dict) -> None:
        self.persona_insights.append(insight)
