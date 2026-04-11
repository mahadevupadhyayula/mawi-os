from __future__ import annotations

import json
from datetime import datetime, timezone

from context.models import ExecutionContext, OutcomeContext
from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OutcomeRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def record_execution(self, run_id: str, deal_id: str, action_id: str, execution: ExecutionContext) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO execution_logs (
                    execution_id, action_id, run_id, deal_id, status,
                    email_result_json, crm_result_json, tool_events_json,
                    error_code, error_message, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution.execution_id,
                    action_id,
                    run_id,
                    deal_id,
                    execution.status,
                    json.dumps(execution.email_result),
                    json.dumps(execution.crm_result),
                    json.dumps(execution.tool_events),
                    None,
                    None,
                    _now(),
                ),
            )

    def record_outcome(self, run_id: str, deal_id: str, action_id: str, outcome: OutcomeContext) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outcomes (
                    action_id, run_id, deal_id, outcome_label, insight,
                    recommended_adjustment, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    run_id,
                    deal_id,
                    outcome.outcome_label,
                    outcome.insight,
                    outcome.recommended_adjustment,
                    outcome.confidence,
                    _now(),
                ),
            )

    def add_persona_insight(self, persona: str, insight: str, success_rate_hint: float) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO persona_insights (persona, insight, success_rate_hint, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (persona, insight, success_rate_hint, _now()),
            )

    def get_persona_insights(self, persona: str, *, limit: int = 5) -> list[dict]:
        with self.db.tx() as conn:
            rows = conn.execute(
                """
                SELECT id, persona, insight, success_rate_hint, created_at
                FROM persona_insights
                WHERE persona = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (persona, limit),
            ).fetchall()
        return [dict(row) for row in rows]
