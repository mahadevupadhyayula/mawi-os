from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DB_PATH = Path(os.getenv("MAWI_DB_PATH", ".mawi/mawi.db"))


class DBClient:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.tx() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id TEXT PRIMARY KEY,
                    account_name TEXT,
                    contact_name TEXT,
                    persona TEXT,
                    deal_stage TEXT,
                    last_activity_at TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    deal_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS context_envelopes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    source_agent TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, version),
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS actions (
                    action_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    subject TEXT,
                    preview TEXT,
                    body_draft TEXT,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    edited_by TEXT,
                    edited_at TEXT,
                    rejected_by TEXT,
                    rejected_at TEXT,
                    rejection_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS action_steps (
                    step_id TEXT PRIMARY KEY,
                    action_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    step_order INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    subject TEXT,
                    preview TEXT,
                    body_draft TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(action_id, step_order),
                    FOREIGN KEY (action_id) REFERENCES actions(action_id),
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS execution_logs (
                    execution_id TEXT PRIMARY KEY,
                    action_id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    email_result_json TEXT NOT NULL,
                    crm_result_json TEXT NOT NULL,
                    tool_events_json TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    executed_at TEXT NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES actions(action_id),
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    outcome_label TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    recommended_adjustment TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES actions(action_id),
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );

                CREATE TABLE IF NOT EXISTS persona_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    success_rate_hint REAL NOT NULL,
                    source_outcome_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_outcome_id) REFERENCES outcomes(outcome_id)
                );
                """
            )
