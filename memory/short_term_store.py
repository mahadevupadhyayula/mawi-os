from __future__ import annotations

from context.schemas import ContextEnvelope
from memory.repository import InMemoryRepository


class ShortTermMemory:
    def __init__(self) -> None:
        self.repo = InMemoryRepository()

    def save_envelope(self, envelope: ContextEnvelope) -> None:
        self.repo.set(envelope.meta.workflow_run_id, envelope)

    def get_envelope(self, workflow_run_id: str) -> ContextEnvelope | None:
        return self.repo.get(workflow_run_id)
