"""
Purpose:
Memory module `memory_models` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActionRecord:
    action_id: str
    deal_id: str
    status: str
    preview: str
    confidence: float
    created_at: str = field(default_factory=now_iso)


@dataclass
class OutcomeRecord:
    deal_id: str
    action_id: str
    outcome_label: str
    insight: str
    created_at: str = field(default_factory=now_iso)


@dataclass
class PersonaInsight:
    persona: str
    insight: str
    success_rate_hint: float
    created_at: str = field(default_factory=now_iso)
