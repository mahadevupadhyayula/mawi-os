"""
Purpose:
Memory module `short_term_store` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict

from context.models import ContextEnvelope


class ShortTermMemory:
    def __init__(self) -> None:
        self._runs: Dict[str, dict] = {}

    def save(self, run_id: str, envelope: ContextEnvelope) -> None:
        self._runs[run_id] = asdict(envelope)

    def get(self, run_id: str) -> dict | None:
        return self._runs.get(run_id)
