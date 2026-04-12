from __future__ import annotations

import json
from hashlib import sha256
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

    def assign_variant(self, *, run_id: str, workflow_id: str) -> dict[str, str]:
        rollout = self._get_or_create_rollout(workflow_id)
        digest = sha256(f"{workflow_id}:{run_id}".encode("utf-8")).hexdigest()
        bucket_score = int(digest[:8], 16) / 0xFFFFFFFF
        bucket = "A" if bucket_score < 0.5 else "B"
        assigned_variant = bucket

        phase = str(rollout["rollout_phase"])
        if phase == "shadow":
            effective_variant = str(rollout["promoted_default_variant"])
        elif phase == "canary":
            effective_variant = "B" if bucket_score < float(rollout["canary_percent"]) else "A"
        elif phase == "full":
            effective_variant = "B"
        else:
            effective_variant = "A"

        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO prompt_variant_assignments (
                    run_id, workflow_id, bucket, assigned_variant, effective_variant, rollout_phase, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, workflow_id) DO UPDATE SET
                    bucket=excluded.bucket,
                    assigned_variant=excluded.assigned_variant,
                    effective_variant=excluded.effective_variant,
                    rollout_phase=excluded.rollout_phase
                """,
                (run_id, workflow_id, bucket, assigned_variant, effective_variant, phase, now),
            )
            conn.execute(
                """
                INSERT INTO prompt_variant_metrics (workflow_id, variant, exposures, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(workflow_id, variant) DO UPDATE SET
                    exposures=prompt_variant_metrics.exposures + 1,
                    updated_at=excluded.updated_at
                """,
                (workflow_id, effective_variant, now),
            )
        return {"bucket": bucket, "assigned_variant": assigned_variant, "effective_variant": effective_variant, "rollout_phase": phase}

    def record_outcome_metrics(
        self,
        *,
        run_id: str,
        reply_received: bool,
        meeting_booked: bool,
        execution_success: bool,
    ) -> None:
        with self.db.tx() as conn:
            row = conn.execute(
                """
                SELECT workflow_id, effective_variant
                FROM prompt_variant_assignments
                WHERE run_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if not row:
                return
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO prompt_variant_metrics (
                    workflow_id, variant, exposures, replies, meetings, execution_successes, rejections, updated_at
                ) VALUES (?, ?, 0, ?, ?, ?, 0, ?)
                ON CONFLICT(workflow_id, variant) DO UPDATE SET
                    exposures=prompt_variant_metrics.exposures + 1,
                    replies=prompt_variant_metrics.replies + excluded.replies,
                    meetings=prompt_variant_metrics.meetings + excluded.meetings,
                    execution_successes=prompt_variant_metrics.execution_successes + excluded.execution_successes,
                    updated_at=excluded.updated_at
                """,
                (
                    str(row["workflow_id"]),
                    str(row["effective_variant"]),
                    1 if reply_received else 0,
                    1 if meeting_booked else 0,
                    1 if execution_success else 0,
                    now,
                ),
            )
            self._evaluate_rollout_health(conn, workflow_id=str(row["workflow_id"]))

    def record_rejection(self, *, action_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            row = conn.execute(
                """
                SELECT a.run_id, p.workflow_id, p.effective_variant
                FROM actions a
                JOIN prompt_variant_assignments p ON p.run_id = a.run_id
                WHERE a.action_id=?
                ORDER BY p.id DESC
                LIMIT 1
                """,
                (action_id,),
            ).fetchone()
            if not row:
                return
            conn.execute(
                """
                INSERT INTO prompt_variant_metrics (
                    workflow_id, variant, exposures, replies, meetings, execution_successes, rejections, updated_at
                ) VALUES (?, ?, 0, 0, 0, 0, 1, ?)
                ON CONFLICT(workflow_id, variant) DO UPDATE SET
                    exposures=prompt_variant_metrics.exposures + 1,
                    rejections=prompt_variant_metrics.rejections + 1,
                    updated_at=excluded.updated_at
                """,
                (str(row["workflow_id"]), str(row["effective_variant"]), now),
            )
            self._evaluate_rollout_health(conn, workflow_id=str(row["workflow_id"]))

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
            rollout_rows = conn.execute(
                """
                SELECT workflow_id, rollout_phase, canary_percent, promoted_default_variant,
                       active_release_id, previous_stable_release_id, workflow_release_version, updated_at
                FROM prompt_variant_rollouts
                ORDER BY workflow_id ASC
                """
            ).fetchall()
            variant_rows = conn.execute(
                """
                SELECT workflow_id, variant, exposures, replies, meetings, execution_successes, rejections, updated_at
                FROM prompt_variant_metrics
                ORDER BY workflow_id ASC, variant ASC
                """
            ).fetchall()
            changelog_rows = conn.execute(
                """
                SELECT workflow_id, change_type, previous_value, new_value, note, created_at
                FROM prompt_variant_changelog
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            agent_rows = conn.execute(
                """
                SELECT
                    agent_id,
                    COUNT(*) AS total_runs,
                    SUM(CASE WHEN error_type = 'KeyError' THEN 1 ELSE 0 END) AS parse_failures,
                    SUM(CASE WHEN error_type = 'PromptLintError' THEN 1 ELSE 0 END) AS lint_policy_violations,
                    SUM(CASE WHEN outcome_label IS NOT NULL THEN 1 ELSE 0 END) AS outcome_samples,
                    SUM(CASE WHEN outcome_label IN ('positive', 'positive_engagement') THEN 1 ELSE 0 END) AS positive_outcomes,
                    COALESCE(AVG(CASE WHEN outcome_label IN ('positive', 'positive_engagement') THEN confidence END), 0) AS pos_confidence,
                    COALESCE(AVG(CASE WHEN outcome_label IS NOT NULL AND outcome_label NOT IN ('positive', 'positive_engagement') THEN confidence END), 0) AS neg_confidence
                FROM prompt_runs
                GROUP BY agent_id
                ORDER BY agent_id ASC
                """
            ).fetchall()
            execution_policy_violations = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM action_steps WHERE last_error = 'generated_output_policy_violation'"
                ).fetchone()["c"]
            )
            approval_rejection_rows = conn.execute(
                """
                WITH latest_state AS (
                    SELECT ws.run_id, ws.deal_id, ws.stage
                    FROM workflow_state ws
                    JOIN (
                        SELECT run_id, deal_id, MAX(updated_at) AS latest_updated_at
                        FROM workflow_state
                        GROUP BY run_id, deal_id
                    ) latest
                    ON latest.run_id = ws.run_id
                       AND latest.deal_id = ws.deal_id
                       AND latest.latest_updated_at = ws.updated_at
                )
                SELECT
                    COALESCE(ls.stage, 'unknown') AS stage,
                    COUNT(*) AS total_actions,
                    SUM(CASE WHEN a.status = 'rejected' OR a.rejected_at IS NOT NULL THEN 1 ELSE 0 END) AS rejected_actions
                FROM actions a
                LEFT JOIN latest_state ls ON ls.run_id = a.run_id AND ls.deal_id = a.deal_id
                GROUP BY COALESCE(ls.stage, 'unknown')
                ORDER BY stage ASC
                """
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
        rollout_state = [dict(row) for row in rollout_rows]
        variant_metrics = [
            {
                "workflow_id": str(row["workflow_id"]),
                "variant": str(row["variant"]),
                "exposures": int(row["exposures"]),
                "reply_rate": (int(row["replies"]) / int(row["exposures"])) if int(row["exposures"]) else 0.0,
                "meeting_rate": (int(row["meetings"]) / int(row["exposures"])) if int(row["exposures"]) else 0.0,
                "execution_success_rate": (int(row["execution_successes"]) / int(row["exposures"])) if int(row["exposures"]) else 0.0,
                "rejection_rate": (int(row["rejections"]) / int(row["exposures"])) if int(row["exposures"]) else 0.0,
                "updated_at": str(row["updated_at"]),
            }
            for row in variant_rows
        ]
        changelog = [dict(row) for row in changelog_rows]
        baseline_outcome_samples = sum(int(row["outcome_samples"]) for row in agent_rows)
        baseline_positive = sum(int(row["positive_outcomes"]) for row in agent_rows)
        baseline_positive_rate = (baseline_positive / baseline_outcome_samples) if baseline_outcome_samples else 0.0
        agent_metrics: list[dict[str, Any]] = []
        for row in agent_rows:
            total_runs = int(row["total_runs"])
            parse_failures_for_agent = int(row["parse_failures"])
            lint_policy_violations = int(row["lint_policy_violations"])
            outcome_samples = int(row["outcome_samples"])
            positive_outcomes = int(row["positive_outcomes"])
            policy_violations = lint_policy_violations
            if str(row["agent_id"]) == "execution_agent":
                policy_violations += execution_policy_violations
            outcome_rate = (positive_outcomes / outcome_samples) if outcome_samples else 0.0
            agent_metrics.append(
                {
                    "agent_id": str(row["agent_id"]),
                    "total_runs": total_runs,
                    "parse_failure_rate": (parse_failures_for_agent / total_runs) if total_runs else 0.0,
                    "policy_violation_rate": (policy_violations / total_runs) if total_runs else 0.0,
                    "policy_violations": policy_violations,
                    "approval_rejection_rate_by_stage": [
                        {
                            "stage": str(stage_row["stage"]),
                            "total_actions": int(stage_row["total_actions"]),
                            "rejected_actions": int(stage_row["rejected_actions"]),
                            "rejection_rate": (
                                int(stage_row["rejected_actions"]) / int(stage_row["total_actions"])
                                if int(stage_row["total_actions"])
                                else 0.0
                            ),
                        }
                        for stage_row in approval_rejection_rows
                    ],
                    "downstream_outcome_lift_correlation": {
                        "outcome_samples": outcome_samples,
                        "positive_outcome_rate": outcome_rate,
                        "baseline_positive_outcome_rate": baseline_positive_rate,
                        "lift": outcome_rate - baseline_positive_rate,
                        "confidence_delta": float(row["pos_confidence"]) - float(row["neg_confidence"]),
                    },
                }
            )

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
                "agent_metrics": agent_metrics,
            },
            "experiments": {
                "rollouts": rollout_state,
                "variant_metrics": variant_metrics,
                "promotion_changelog": changelog,
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

    def _get_or_create_rollout(self, workflow_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO prompt_variant_rollouts (
                    workflow_id, rollout_phase, canary_percent,
                    degradation_reply_threshold, degradation_meeting_threshold,
                    degradation_execution_threshold, degradation_rejection_threshold,
                    promoted_default_variant, active_release_id, previous_stable_release_id,
                    workflow_release_version, updated_at
                ) VALUES (?, 'shadow', 0.1, 0.05, 0.03, 0.05, 0.05, 'A', '', '', 'unversioned', ?)
                ON CONFLICT(workflow_id) DO NOTHING
                """,
                (workflow_id, now),
            )
            row = conn.execute("SELECT * FROM prompt_variant_rollouts WHERE workflow_id=?", (workflow_id,)).fetchone()
        return dict(row) if row else {"workflow_id": workflow_id, "rollout_phase": "shadow", "canary_percent": 0.1, "promoted_default_variant": "A"}

    def register_prompt_release(
        self,
        *,
        release_id: str,
        workflow_id: str,
        workflow_release_version: str,
        prompt_profile_version: str,
        owner: str,
        status: str,
        changelog_note: str,
    ) -> None:
        if not changelog_note.strip():
            raise ValueError("Prompt release updates require a changelog_note.")
        if status not in {"draft", "active", "deprecated"}:
            raise ValueError("status must be one of: draft, active, deprecated.")
        self._get_or_create_rollout(workflow_id)
        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            previous_stable_row = conn.execute(
                """
                SELECT release_id
                FROM prompt_release_sets
                WHERE workflow_id=? AND status='active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workflow_id,),
            ).fetchone()
            previous_stable_release_id = str(previous_stable_row["release_id"]) if previous_stable_row else None
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_release_sets (
                    release_id, workflow_id, workflow_release_version, prompt_profile_version,
                    status, owner, changelog_note, previous_stable_release_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    workflow_id,
                    workflow_release_version,
                    prompt_profile_version,
                    status,
                    owner,
                    changelog_note,
                    previous_stable_release_id,
                    now,
                ),
            )
            if status == "active":
                conn.execute(
                    """
                    UPDATE prompt_variant_rollouts
                    SET previous_stable_release_id = COALESCE(NULLIF(active_release_id, ''), previous_stable_release_id),
                        active_release_id = ?,
                        workflow_release_version = ?,
                        updated_at = ?
                    WHERE workflow_id = ?
                    """,
                    (release_id, workflow_release_version, now, workflow_id),
                )

    def record_promotion_approval(
        self,
        *,
        workflow_id: str,
        release_id: str,
        approver: str,
        decision: str,
        note: str,
    ) -> None:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be 'approved' or 'rejected'.")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO prompt_promotion_approvals (
                    workflow_id, release_id, approver, decision, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (workflow_id, release_id, approver, decision, note, now),
            )

    def _evaluate_rollout_health(self, conn: Any, *, workflow_id: str) -> None:
        rollout = conn.execute("SELECT * FROM prompt_variant_rollouts WHERE workflow_id=?", (workflow_id,)).fetchone()
        if not rollout:
            return
        metrics_rows = conn.execute(
            "SELECT * FROM prompt_variant_metrics WHERE workflow_id=?",
            (workflow_id,),
        ).fetchall()
        metrics = {str(row["variant"]): row for row in metrics_rows}
        control = metrics.get("A")
        candidate = metrics.get("B")
        if control is None or candidate is None or int(candidate["exposures"]) < 10:
            if control is not None and str(rollout["rollout_phase"]) == "shadow" and int(control["exposures"]) >= 20:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE prompt_variant_rollouts SET rollout_phase='canary', updated_at=? WHERE workflow_id=?",
                    (now, workflow_id),
                )
                conn.execute(
                    """
                    INSERT INTO prompt_variant_changelog (workflow_id, change_type, previous_value, new_value, note, created_at)
                    VALUES (?, 'phase_advance', ?, 'canary', 'Advanced from shadow mode to low-traffic canary.', ?)
                    """,
                    (workflow_id, str(rollout["rollout_phase"]), now),
                )
            return

        def rate(row: Any, key: str) -> float:
            exposures = max(int(row["exposures"]), 1)
            return float(row[key]) / exposures

        degraded = (
            rate(control, "replies") - rate(candidate, "replies") > float(rollout["degradation_reply_threshold"])
            or rate(control, "meetings") - rate(candidate, "meetings") > float(rollout["degradation_meeting_threshold"])
            or rate(control, "execution_successes") - rate(candidate, "execution_successes") > float(rollout["degradation_execution_threshold"])
            or rate(candidate, "rejections") - rate(control, "rejections") > float(rollout["degradation_rejection_threshold"])
        )
        now = datetime.now(timezone.utc).isoformat()
        if degraded and str(rollout["rollout_phase"]) != "shadow":
            conn.execute(
                """
                UPDATE prompt_variant_rollouts
                SET rollout_phase='shadow',
                    promoted_default_variant='A',
                    active_release_id=COALESCE(NULLIF(previous_stable_release_id, ''), active_release_id),
                    updated_at=?
                WHERE workflow_id=?
                """,
                (now, workflow_id),
            )
            conn.execute(
                """
                INSERT INTO prompt_variant_changelog (workflow_id, change_type, previous_value, new_value, note, created_at)
                VALUES (?, 'auto_rollback', ?, 'shadow:A', 'Automatic rollback triggered by degradation thresholds.', ?)
                """,
                (workflow_id, f"{rollout['rollout_phase']}:{rollout['promoted_default_variant']}", now),
            )
            return

        better = (
            rate(candidate, "replies") >= rate(control, "replies")
            and rate(candidate, "meetings") >= rate(control, "meetings")
            and rate(candidate, "execution_successes") >= rate(control, "execution_successes")
            and rate(candidate, "rejections") <= rate(control, "rejections")
        )
        if better and int(candidate["exposures"]) >= 25 and str(rollout["promoted_default_variant"]) != "B":
            active_release_id = str(rollout["active_release_id"] or "")
            if not active_release_id:
                return
            approval_counts = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN decision='approved' THEN 1 ELSE 0 END) AS approvals,
                    SUM(CASE WHEN decision='rejected' THEN 1 ELSE 0 END) AS rejections
                FROM prompt_promotion_approvals
                WHERE workflow_id=? AND release_id=?
                """,
                (workflow_id, active_release_id),
            ).fetchone()
            if not approval_counts:
                return
            approvals = int(approval_counts["approvals"] or 0)
            rejections = int(approval_counts["rejections"] or 0)
            if approvals < 2 or rejections > 0:
                return
            conn.execute(
                "UPDATE prompt_variant_rollouts SET promoted_default_variant='B', rollout_phase='full', updated_at=? WHERE workflow_id=?",
                (now, workflow_id),
            )
            conn.execute(
                """
                INSERT INTO prompt_variant_changelog (workflow_id, change_type, previous_value, new_value, note, created_at)
                VALUES (?, 'promotion', ?, 'full:B', 'Promoted winning B variant to default after sustained improvement.', ?)
                """,
                (workflow_id, f"{rollout['rollout_phase']}:{rollout['promoted_default_variant']}", now),
            )
