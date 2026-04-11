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
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    execution_result_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT NOT NULL DEFAULT '',
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

                CREATE TABLE IF NOT EXISTS execution_step_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    step_order INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(execution_id, step_id),
                    FOREIGN KEY (execution_id) REFERENCES execution_logs(execution_id),
                    FOREIGN KEY (action_id) REFERENCES actions(action_id),
                    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id),
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                );


                CREATE TABLE IF NOT EXISTS prompt_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    prompt_profile_id TEXT NOT NULL,
                    prompt_profile_version TEXT NOT NULL,
                    prompt_schema_version TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_type TEXT,
                    fallback_used INTEGER NOT NULL DEFAULT 0,
                    confidence REAL,
                    outcome_label TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_traces (
                    trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_counters (
                    metric_name TEXT PRIMARY KEY,
                    metric_value INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS prompt_variant_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    assigned_variant TEXT NOT NULL,
                    effective_variant TEXT NOT NULL,
                    rollout_phase TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, workflow_id)
                );

                CREATE TABLE IF NOT EXISTS prompt_variant_rollouts (
                    workflow_id TEXT PRIMARY KEY,
                    rollout_phase TEXT NOT NULL DEFAULT 'shadow',
                    canary_percent REAL NOT NULL DEFAULT 0.1,
                    degradation_reply_threshold REAL NOT NULL DEFAULT 0.05,
                    degradation_meeting_threshold REAL NOT NULL DEFAULT 0.03,
                    degradation_execution_threshold REAL NOT NULL DEFAULT 0.05,
                    degradation_rejection_threshold REAL NOT NULL DEFAULT 0.05,
                    promoted_default_variant TEXT NOT NULL DEFAULT 'A',
                    active_release_id TEXT NOT NULL DEFAULT '',
                    previous_stable_release_id TEXT NOT NULL DEFAULT '',
                    workflow_release_version TEXT NOT NULL DEFAULT 'unversioned',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_variant_metrics (
                    workflow_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    exposures INTEGER NOT NULL DEFAULT 0,
                    replies INTEGER NOT NULL DEFAULT 0,
                    meetings INTEGER NOT NULL DEFAULT 0,
                    execution_successes INTEGER NOT NULL DEFAULT 0,
                    rejections INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, variant)
                );

                CREATE TABLE IF NOT EXISTS prompt_variant_changelog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    previous_value TEXT,
                    new_value TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_release_sets (
                    release_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_release_version TEXT NOT NULL,
                    prompt_profile_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    changelog_note TEXT NOT NULL,
                    previous_stable_release_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_promotion_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "action_steps", "retry_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "action_steps", "execution_result_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "action_steps", "last_error", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "prompt_variant_rollouts", "active_release_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "prompt_variant_rollouts", "previous_stable_release_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "prompt_variant_rollouts", "workflow_release_version", "TEXT NOT NULL DEFAULT 'unversioned'")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
