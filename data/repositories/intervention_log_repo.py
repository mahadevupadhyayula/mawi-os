from __future__ import annotations

import json
from datetime import datetime, timezone

from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InterventionLogRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def insert_log(
        self,
        *,
        run_id: str,
        deal_id: str,
        intervention_type: str,
        status: str,
        details: dict | None = None,
    ) -> int:
        now = _now()
        with self.db.tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO intervention_logs (
                    run_id, deal_id, intervention_type, status, details_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, deal_id, intervention_type, status, json.dumps(details or {}), now, now),
            )
            return int(cursor.lastrowid)

    def list_logs(self, *, run_id: str | None = None, deal_id: str | None = None, limit: int = 100) -> list[dict]:
        if run_id is None and deal_id is None:
            raise ValueError("Either run_id or deal_id must be provided")

        clauses: list[str] = []
        params: list[object] = []
        if run_id is not None:
            clauses.append("run_id=?")
            params.append(run_id)
        if deal_id is not None:
            clauses.append("deal_id=?")
            params.append(deal_id)

        params.append(limit)
        query = f"""
            SELECT *
            FROM intervention_logs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """

        with self.db.tx() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_log(self, log_id: int, *, status: str, details: dict | None = None) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                UPDATE intervention_logs
                SET status=?,
                    details_json=COALESCE(?, details_json),
                    updated_at=?
                WHERE id=?
                """,
                (status, json.dumps(details) if details is not None else None, _now(), log_id),
            )
