from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from data.db_client import DBClient


class PromptDiagnosticsRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def log_render_event(
        self,
        *,
        run_id: str,
        workflow_id: str,
        agent_id: str,
        prompt_name: str,
        prompt_profile_id: str,
        prompt_profile_version: str,
        prompt_schema_version: str,
        latency_ms: int,
        status: str,
        fallback_used: bool,
        error_type: str | None = None,
        confidence: float | None = None,
        trace_sampled: bool = False,
        trace_payload: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO prompt_runs (
                    run_id,
                    workflow_id,
                    agent_id,
                    prompt_name,
                    prompt_profile_id,
                    prompt_profile_version,
                    prompt_schema_version,
                    latency_ms,
                    status,
                    error_type,
                    fallback_used,
                    confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workflow_id,
                    agent_id,
                    prompt_name,
                    prompt_profile_id,
                    prompt_profile_version,
                    prompt_schema_version,
                    latency_ms,
                    status,
                    error_type,
                    1 if fallback_used else 0,
                    confidence,
                    now,
                ),
            )
            if trace_sampled and trace_payload is not None:
                conn.execute(
                    """
                    INSERT INTO prompt_traces (
                        run_id,
                        workflow_id,
                        agent_id,
                        prompt_name,
                        trace_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, workflow_id, agent_id, prompt_name, json.dumps(trace_payload, sort_keys=True), now),
                )

    def increment_counter(self, *, metric_name: str, metric_value: int = 1) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO prompt_counters (metric_name, metric_value)
                VALUES (?, ?)
                ON CONFLICT(metric_name) DO UPDATE SET metric_value = metric_value + excluded.metric_value
                """,
                (metric_name, metric_value),
            )

    def attach_outcome_label(self, *, run_id: str, outcome_label: str) -> None:
        with self.db.tx() as conn:
            conn.execute("UPDATE prompt_runs SET outcome_label = ? WHERE run_id = ?", (outcome_label, run_id))

    def diagnostics_report(self, *, limit: int = 25) -> dict[str, Any]:
        with self.db.tx() as conn:
            total = int(conn.execute("SELECT COUNT(*) AS c FROM prompt_runs").fetchone()["c"])
            failures = int(conn.execute("SELECT COUNT(*) AS c FROM prompt_runs WHERE status = 'error'").fetchone()["c"])
            parse_failures = self._counter_value(conn, "parse_failures")
            schema_failures = self._counter_value(conn, "schema_validation_errors")
            fallback_count = int(conn.execute("SELECT COUNT(*) AS c FROM prompt_runs WHERE fallback_used = 1").fetchone()["c"])
            latency = conn.execute(
                "SELECT COALESCE(AVG(latency_ms), 0) AS avg_ms, COALESCE(MAX(latency_ms), 0) AS max_ms FROM prompt_runs"
            ).fetchone()
            confidence_rows = conn.execute(
                """
                SELECT
                    CASE
                        WHEN confidence < 0.5 THEN 'low'
                        WHEN confidence < 0.8 THEN 'medium'
                        ELSE 'high'
                    END AS band,
                    COUNT(*) AS count
                FROM prompt_runs
                WHERE confidence IS NOT NULL
                GROUP BY band
                """
            ).fetchall()
            outcome_rows = conn.execute(
                """
                SELECT outcome_label, COUNT(*) AS count, COALESCE(AVG(confidence), 0) AS avg_confidence
                FROM prompt_runs
                WHERE outcome_label IS NOT NULL
                GROUP BY outcome_label
                ORDER BY count DESC
                """
            ).fetchall()
            recent_traces = conn.execute(
                """
                SELECT trace_id, run_id, workflow_id, agent_id, prompt_name, trace_json, created_at
                FROM prompt_traces
                ORDER BY trace_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        confidence_distribution = {str(row["band"]): int(row["count"]) for row in confidence_rows}
        outcome_correlation = [
            {
                "outcome_label": str(row["outcome_label"]),
                "count": int(row["count"]),
                "avg_confidence": float(row["avg_confidence"]),
            }
            for row in outcome_rows
        ]
        traces = [
            {
                "trace_id": int(row["trace_id"]),
                "run_id": str(row["run_id"]),
                "workflow_id": str(row["workflow_id"]),
                "agent_id": str(row["agent_id"]),
                "prompt_name": str(row["prompt_name"]),
                "trace": json.loads(str(row["trace_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in recent_traces
        ]

        fallback_rate = (fallback_count / total) if total else 0.0
        return {
            "summary": {
                "total_prompt_runs": total,
                "error_prompt_runs": failures,
                "parse_failures": parse_failures,
                "schema_validation_errors": schema_failures,
                "fallback_count": fallback_count,
                "fallback_usage_rate": fallback_rate,
            },
            "performance": {
                "avg_latency_ms": float(latency["avg_ms"]),
                "max_latency_ms": int(latency["max_ms"]),
                "confidence_distribution": confidence_distribution,
                "outcome_correlation": outcome_correlation,
            },
            "sampled_traces": traces,
        }

    def _counter_value(self, conn: Any, metric_name: str) -> int:
        row = conn.execute(
            "SELECT metric_value FROM prompt_counters WHERE metric_name = ?",
            (metric_name,),
        ).fetchone()
        if row is None:
            return 0
        return int(row["metric_value"] or 0)
