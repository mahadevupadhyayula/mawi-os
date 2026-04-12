from __future__ import annotations

import json
from datetime import datetime, timezone

from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CRMSyncLogRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def insert_log(
        self,
        *,
        run_id: str,
        deal_id: str,
        sync_status: str,
        request: dict | None = None,
        response: dict | None = None,
        error_message: str | None = None,
        synced_at: str | None = None,
    ) -> int:
        now = _now()
        with self.db.tx() as conn:
            cursor = conn.execute(
                """
                INSERT INTO crm_sync_logs (
                    run_id, deal_id, sync_status, request_json, response_json, error_message,
                    synced_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    deal_id,
                    sync_status,
                    json.dumps(request or {}),
                    json.dumps(response or {}),
                    error_message,
                    synced_at,
                    now,
                    now,
                ),
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
            FROM crm_sync_logs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """

        with self.db.tx() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_log(
        self,
        log_id: int,
        *,
        sync_status: str,
        response: dict | None = None,
        error_message: str | None = None,
        synced_at: str | None = None,
    ) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                UPDATE crm_sync_logs
                SET sync_status=?,
                    response_json=COALESCE(?, response_json),
                    error_message=?,
                    synced_at=COALESCE(?, synced_at),
                    updated_at=?
                WHERE id=?
                """,
                (
                    sync_status,
                    json.dumps(response) if response is not None else None,
                    error_message,
                    synced_at,
                    _now(),
                    log_id,
                ),
            )
