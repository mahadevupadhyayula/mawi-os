from __future__ import annotations

import json
from datetime import datetime, timezone

from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStateRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def upsert_state(
        self,
        *,
        run_id: str,
        deal_id: str,
        stage: str,
        status: str,
        state: dict | None = None,
        workflow_name: str | None = None,
    ) -> None:
        now = _now()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO workflow_state (
                    run_id, deal_id, workflow_name, stage, status, state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, deal_id) DO UPDATE SET
                    workflow_name=COALESCE(excluded.workflow_name, workflow_state.workflow_name),
                    stage=excluded.stage,
                    status=excluded.status,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (run_id, deal_id, workflow_name, stage, status, json.dumps(state or {}), now, now),
            )

    def get_state(self, *, run_id: str | None = None, deal_id: str | None = None) -> dict | None:
        if run_id is None and deal_id is None:
            raise ValueError("Either run_id or deal_id must be provided")

        with self.db.tx() as conn:
            if run_id is not None and deal_id is not None:
                row = conn.execute(
                    "SELECT * FROM workflow_state WHERE run_id=? AND deal_id=?",
                    (run_id, deal_id),
                ).fetchone()
            elif run_id is not None:
                row = conn.execute(
                    "SELECT * FROM workflow_state WHERE run_id=?",
                    (run_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT *
                    FROM workflow_state
                    WHERE deal_id=?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (deal_id,),
                ).fetchone()
        return dict(row) if row else None

    def update_state(
        self,
        *,
        run_id: str,
        deal_id: str,
        stage: str | None = None,
        status: str | None = None,
        state: dict | None = None,
    ) -> None:
        if stage is None and status is None and state is None:
            return

        with self.db.tx() as conn:
            current = conn.execute(
                "SELECT stage, status, state_json FROM workflow_state WHERE run_id=? AND deal_id=?",
                (run_id, deal_id),
            ).fetchone()
            if current is None:
                raise ValueError(f"No workflow_state found for run_id={run_id}, deal_id={deal_id}")

            conn.execute(
                """
                UPDATE workflow_state
                SET stage=?,
                    status=?,
                    state_json=?,
                    updated_at=?
                WHERE run_id=? AND deal_id=?
                """,
                (
                    stage if stage is not None else str(current["stage"]),
                    status if status is not None else str(current["status"]),
                    json.dumps(state) if state is not None else str(current["state_json"]),
                    _now(),
                    run_id,
                    deal_id,
                ),
            )
