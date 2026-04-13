from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data.repositories.outcome_repo import OutcomeRepository
from memory.long_term_store import LongTermMemory
from memory.memory_models import PersonaInsight
from memory.retrieval import retrieve_persona_evidence


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_retrieve_persona_evidence_ranks_recent_before_stale(reset_db) -> None:
    memory = LongTermMemory()
    repo = OutcomeRepository()

    repo.add_persona_insight("vp_sales", "Old ROI evidence", 0.95)
    repo.add_persona_insight("vp_sales", "Recent ROI evidence", 0.55)
    with repo.db.tx() as conn:
        conn.execute("UPDATE persona_insights SET created_at=? WHERE insight=?", (_iso(120), "Old ROI evidence"))
        conn.execute("UPDATE persona_insights SET created_at=? WHERE insight=?", (_iso(3), "Recent ROI evidence"))

    evidence = retrieve_persona_evidence(memory=memory, outcome_repo=repo, persona="vp_sales", max_items=2)

    assert len(evidence) == 2
    assert evidence[0]["snippet"] == "Recent ROI evidence"


def test_retrieve_persona_evidence_honors_min_quality_threshold(reset_db) -> None:
    memory = LongTermMemory()
    repo = OutcomeRepository()
    memory.add_insight(
        PersonaInsight(persona="vp_sales", insight="Very stale weak evidence", success_rate_hint=0.15, created_at=_iso(365))
    )

    evidence = retrieve_persona_evidence(
        memory=memory,
        outcome_repo=repo,
        persona="vp_sales",
        max_items=5,
        min_quality_score=0.2,
    )

    assert evidence == []
