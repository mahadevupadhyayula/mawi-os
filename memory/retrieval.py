"""
Purpose:
Memory module `retrieval` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from memory.long_term_store import LongTermMemory


def retrieve_persona_insights(memory: LongTermMemory, persona: str) -> list[str]:
    return [entry.insight for entry in memory.insights_for_persona(persona)]
