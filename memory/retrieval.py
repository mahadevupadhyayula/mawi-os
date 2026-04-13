"""
Purpose:
Memory module `retrieval` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from datetime import datetime, timezone

from memory.long_term_store import LongTermMemory
from data.repositories.outcome_repo import OutcomeRepository


def retrieve_persona_insights(memory: LongTermMemory, persona: str) -> list[str]:
    return [entry.insight for entry in memory.insights_for_persona(persona)]


def _parse_iso_timestamp(raw: str | None) -> datetime:
    if not raw:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _recency_multiplier(created_at: str | None, *, now: datetime) -> float:
    age_seconds = max(0.0, (now - _parse_iso_timestamp(created_at)).total_seconds())
    age_days = age_seconds / 86_400
    if age_days <= 14:
        return 1.0
    if age_days <= 45:
        return 0.85
    if age_days <= 90:
        return 0.7
    return 0.5


def retrieve_persona_evidence(
    *,
    memory: LongTermMemory,
    outcome_repo: OutcomeRepository,
    persona: str,
    max_items: int = 5,
    min_quality_score: float = 0.01,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    in_memory = [
        {
            "id": f"ltm:{index}",
            "snippet": entry.insight,
            "confidence_impact": round(entry.success_rate_hint * 0.05, 3),
            "quality_score": round(entry.success_rate_hint * _recency_multiplier(entry.created_at, now=now), 3),
            "source": "long_term_memory",
            "created_at": entry.created_at,
        }
        for index, entry in enumerate(memory.insights_for_persona(persona), start=1)
    ]
    repo_rows = outcome_repo.get_persona_insights(persona, limit=max_items)
    in_repo = [
        {
            "id": f"repo:{row['id']}",
            "snippet": row["insight"],
            "confidence_impact": round(float(row["success_rate_hint"]) * 0.05, 3),
            "quality_score": round(
                float(row["success_rate_hint"]) * _recency_multiplier(str(row.get("created_at")), now=now),
                3,
            ),
            "source": "persona_insights_repository",
            "created_at": str(row.get("created_at") or ""),
        }
        for row in repo_rows
    ]
    ranked_inputs = sorted([*in_repo, *in_memory], key=lambda item: float(item.get("quality_score", 0.0)), reverse=True)
    evidence: list[dict] = []
    seen_snippets: set[str] = set()
    for item in ranked_inputs:
        snippet = item["snippet"].strip().lower()
        if snippet in seen_snippets or float(item.get("quality_score", 0.0)) < min_quality_score:
            continue
        seen_snippets.add(snippet)
        evidence.append(item)
        if len(evidence) >= max_items:
            break
    return evidence
