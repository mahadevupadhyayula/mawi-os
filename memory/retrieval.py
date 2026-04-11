"""
Purpose:
Memory module `retrieval` for storing and retrieving workflow history.

Technical Details:
Provides short/long-term data access patterns that support personalization, reasoning reuse, and post-run analytics.
"""

from __future__ import annotations

from memory.long_term_store import LongTermMemory
from data.repositories.outcome_repo import OutcomeRepository


def retrieve_persona_insights(memory: LongTermMemory, persona: str) -> list[str]:
    return [entry.insight for entry in memory.insights_for_persona(persona)]


def retrieve_persona_evidence(
    *,
    memory: LongTermMemory,
    outcome_repo: OutcomeRepository,
    persona: str,
    max_items: int = 5,
) -> list[dict]:
    in_memory = [
        {
            "id": f"ltm:{index}",
            "snippet": entry.insight,
            "confidence_impact": round(entry.success_rate_hint * 0.05, 3),
            "source": "long_term_memory",
        }
        for index, entry in enumerate(memory.insights_for_persona(persona), start=1)
    ]
    repo_rows = outcome_repo.get_persona_insights(persona, limit=max_items)
    in_repo = [
        {
            "id": f"repo:{row['id']}",
            "snippet": row["insight"],
            "confidence_impact": round(float(row["success_rate_hint"]) * 0.05, 3),
            "source": "persona_insights_repository",
        }
        for row in repo_rows
    ]
    evidence: list[dict] = []
    seen_snippets: set[str] = set()
    for item in [*in_repo, *in_memory]:
        snippet = item["snippet"].strip().lower()
        if snippet in seen_snippets:
            continue
        seen_snippets.add(snippet)
        evidence.append(item)
        if len(evidence) >= max_items:
            break
    return evidence
