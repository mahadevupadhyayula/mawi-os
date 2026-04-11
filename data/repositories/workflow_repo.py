from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from context.models import ContextEnvelope
from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def create_or_update_deal(self, deal_id: str, raw_data: dict) -> None:
        now = _now()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO deals (deal_id, account_name, contact_name, persona, deal_stage, last_activity_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(deal_id) DO UPDATE SET
                  account_name=excluded.account_name,
                  contact_name=excluded.contact_name,
                  persona=excluded.persona,
                  deal_stage=excluded.deal_stage,
                  last_activity_at=excluded.last_activity_at,
                  updated_at=excluded.updated_at
                """,
                (
                    deal_id,
                    raw_data.get("account"),
                    raw_data.get("contact_name"),
                    raw_data.get("persona"),
                    raw_data.get("deal_stage"),
                    raw_data.get("last_updated"),
                    now,
                    now,
                ),
            )

    def create_run(self, deal_id: str, workflow_name: str, stage: str, status: str) -> str:
        run_id = str(uuid4())
        now = _now()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs (run_id, deal_id, workflow_name, current_stage, run_status, started_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, deal_id, workflow_name, stage, status, now, now, now),
            )
        return run_id

    def update_run(self, run_id: str, stage: str, status: str, *, last_error: str | None = None, complete: bool = False) -> None:
        now = _now()
        completed_at = now if complete else None
        with self.db.tx() as conn:
            conn.execute(
                """
                UPDATE workflow_runs
                SET current_stage=?, run_status=?, last_error=?, completed_at=COALESCE(?, completed_at), updated_at=?
                WHERE run_id=?
                """,
                (stage, status, last_error, completed_at, now, run_id),
            )

    def append_envelope_snapshot(self, run_id: str, envelope: ContextEnvelope, source_agent: str | None = None) -> None:
        version = len(envelope.history)
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO context_envelopes (run_id, deal_id, version, stage, envelope_json, source_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    envelope.meta.deal_id,
                    max(version, 1),
                    envelope.meta.workflow_stage,
                    json.dumps(asdict(envelope)),
                    source_agent,
                    _now(),
                ),
            )

    def get_latest_envelope(self, deal_id: str) -> dict | None:
        with self.db.tx() as conn:
            row = conn.execute(
                """
                SELECT envelope_json
                FROM context_envelopes
                WHERE deal_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (deal_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["envelope_json"])


    def get_latest_run_id(self, deal_id: str) -> str | None:
        with self.db.tx() as conn:
            row = conn.execute(
                """
                SELECT run_id
                FROM workflow_runs
                WHERE deal_id=?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (deal_id,),
            ).fetchone()
            return str(row["run_id"]) if row else None
