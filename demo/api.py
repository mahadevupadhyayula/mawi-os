"""Demo-only controls built on the existing workflow API and persistence layer."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from api.service import WorkflowAPI
from demo.scenarios import SCENARIO_NAMES, load_scenario, load_scenarios


_SCENARIO_TITLES = {
    "stalled-deal-approval": "Stalled deal approval",
    "rejected-action": "Rejected follow-up action",
    "llm-fallback": "Deterministic LLM fallback",
}


def _duration_ms(started_at: str | None, ended_at: str | None) -> int | None:
    """Return a persisted wall-clock duration without inventing missing evidence."""
    if not started_at or not ended_at:
        return None
    try:
        elapsed = datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
        return max(0, int(elapsed.total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


def _unique_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    return list(dict.fromkeys(str(row[key]) for row in rows if row.get(key)))


class DemoAPI:
    """Read and mutate only the canonical, explicitly marked demo records."""

    def __init__(self, workflow_api: WorkflowAPI) -> None:
        self.workflow_api = workflow_api
        self.db = workflow_api.orchestrator.workflow_repo.db

    def list_scenarios(self) -> list[dict[str, Any]]:
        scenarios = []
        for fixture in load_scenarios():
            approval = fixture["approval"]
            scenarios.append(
                {
                    "scenario_id": fixture["scenario_id"],
                    "title": _SCENARIO_TITLES[fixture["scenario_id"]],
                    "description": fixture["description"],
                    "expected_workflow": fixture["workflow_id"],
                    "expected_approval_behavior": approval["decision"],
                    "fallback_demonstrated": "llm_simulation" in fixture,
                }
            )
        return scenarios

    def start_scenario(self, scenario_id: str) -> dict[str, str]:
        fixture = load_scenario(scenario_id)
        deal_id = str(fixture["deal"]["deal_id"])
        state = self.workflow_api.start_workflow(
            deal_id,
            workflow_name=str(fixture["workflow_id"]),
            trigger_context=dict(fixture["deal"]),
        )
        run_id = self.workflow_api.orchestrator.workflow_repo.get_latest_run_id(deal_id)
        if run_id is None:
            raise ValueError("Demo workflow run was not persisted")
        return {
            "run_id": run_id,
            "workflow_id": str(fixture["workflow_id"]),
            "current_state": str(state["meta"]["workflow_stage"]),
        }

    def reset(self) -> dict[str, int]:
        deal_ids = tuple(str(load_scenario(name)["deal"]["deal_id"]) for name in SCENARIO_NAMES)
        placeholders = ",".join("?" for _ in deal_ids)
        with self.db.tx() as conn:
            run_rows = conn.execute(
                f"SELECT run_id FROM workflow_runs WHERE deal_id IN ({placeholders})", deal_ids
            ).fetchall()
            run_ids = tuple(str(row["run_id"]) for row in run_rows)
            action_ids: tuple[str, ...] = ()
            if run_ids:
                run_placeholders = ",".join("?" for _ in run_ids)
                action_ids = tuple(
                    str(row["action_id"])
                    for row in conn.execute(
                        f"SELECT action_id FROM actions WHERE run_id IN ({run_placeholders})", run_ids
                    ).fetchall()
                )
                for table in (
                    "prompt_traces",
                    "prompt_runs",
                    "prompt_variant_assignments",
                    "execution_step_logs",
                    "outcomes",
                    "execution_logs",
                    "action_steps",
                    "actions",
                    "context_envelopes",
                    "intervention_logs",
                    "crm_sync_logs",
                    "workflow_state",
                    "workflow_runs",
                ):
                    conn.execute(f"DELETE FROM {table} WHERE run_id IN ({run_placeholders})", run_ids)
            deleted = conn.execute(f"DELETE FROM deals WHERE deal_id IN ({placeholders})", deal_ids).rowcount

        for deal_id in deal_ids:
            self.workflow_api._deal_envelopes.pop(deal_id, None)
            self.workflow_api.orchestrator._run_ids.pop(deal_id, None)
        queue = self.workflow_api.orchestrator.queue._actions
        for action_id in action_ids:
            queue.pop(action_id, None)
        return {"deleted_demo_deals": deleted, "deleted_demo_runs": len(run_ids)}

    def timeline(self, run_id: str) -> list[dict[str, Any]]:
        self._require_demo_run(run_id)
        with self.db.tx() as conn:
            rows = conn.execute(
                """
                SELECT stage, envelope_json, source_agent, created_at
                FROM context_envelopes WHERE run_id=? ORDER BY created_at ASC, id ASC
                """,
                (run_id,),
            ).fetchall()
        timeline = []
        for index, row in enumerate(rows):
            envelope = json.loads(row["envelope_json"])
            timeline.append(
                {
                    "stage_name": str(row["stage"]),
                    "status": "current" if index == len(rows) - 1 else "completed",
                    "timestamp": str(row["created_at"]),
                    "summary": {"deal_id": envelope.get("meta", {}).get("deal_id")},
                    "source_agent": row["source_agent"],
                }
            )
        return timeline

    def audit(self, run_id: str) -> list[dict[str, Any]]:
        self._require_demo_run(run_id)
        with self.db.tx() as conn:
            rows = conn.execute(
                """
                SELECT id, stage, source_agent, created_at
                FROM context_envelopes WHERE run_id=? ORDER BY created_at ASC, id ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "event_id": int(row["id"]),
                "stage": str(row["stage"]),
                "source_agent": row["source_agent"],
                "timestamp": str(row["created_at"]),
            }
            for row in rows
        ]

    def telemetry(self, run_id: str) -> dict[str, Any]:
        run = self._require_demo_run(run_id)
        with self.db.tx() as conn:
            action = conn.execute(
                """
                SELECT status, approved_by, rejected_by, rejection_reason
                FROM actions WHERE run_id=? ORDER BY created_at DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            prompt_rows = conn.execute(
                """
                SELECT agent_id, latency_ms, status, error_type, fallback_used,
                       llm_enabled, provider, model, fallback_reason
                FROM prompt_runs WHERE run_id=? ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
            retries = conn.execute(
                "SELECT COALESCE(SUM(retry_count), 0) AS count FROM action_steps WHERE run_id=?", (run_id,)
            ).fetchone()
            execution = conn.execute(
                """
                SELECT status, tool_events_json, error_code
                FROM execution_logs WHERE run_id=? ORDER BY executed_at DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            outcome = conn.execute(
                "SELECT outcome_label FROM outcomes WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)
            ).fetchone()
            envelope = conn.execute(
                "SELECT envelope_json FROM context_envelopes WHERE run_id=? ORDER BY created_at DESC, id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            envelope_rows = conn.execute(
                """
                SELECT stage, source_agent, created_at
                FROM context_envelopes WHERE run_id=? ORDER BY created_at ASC, id ASC
                """,
                (run_id,),
            ).fetchall()
        prompts = [dict(row) for row in prompt_rows]
        fallback_reasons = [
            value for value in _unique_values(prompts, "fallback_reason") if value != "llm_disabled"
        ]
        tool_events = json.loads(execution["tool_events_json"]) if execution else []
        latest_envelope = json.loads(envelope["envelope_json"]) if envelope else {}
        decision = latest_envelope.get("decision_context") or {}
        last_error = None
        if run.get("last_error"):
            try:
                last_error = json.loads(str(run["last_error"]))
            except (TypeError, ValueError):
                last_error = {"error_class": str(run["last_error"])}
        error_classes = _unique_values(prompts, "error_type")
        if execution and execution["error_code"]:
            error_classes.append(str(execution["error_code"]))
        if last_error and last_error.get("error_class"):
            error_classes.append(str(last_error["error_class"]))
        approval_state = str(action["status"]) if action else "not_required"
        if prompts:
            stage_runs = [
                {
                    "stage": str(row["agent_id"]),
                    "duration_ms": int(row["latency_ms"]),
                    "status": str(row["status"]),
                    "error_class": row["error_type"],
                }
                for row in prompts
            ]
        else:
            persisted_stages = [dict(row) for row in envelope_rows]
            stage_runs = []
            for index, row in enumerate(persisted_stages):
                prior = persisted_stages[index - 1]["created_at"] if index else run["started_at"]
                stage_runs.append(
                    {
                        "stage": str(row["source_agent"] or row["stage"]),
                        "duration_ms": _duration_ms(str(prior), str(row["created_at"])),
                        "status": "completed",
                        "error_class": None,
                    }
                )
        return {
            "workflow_id": str(run["workflow_name"]),
            "current_status": str(run["run_status"]),
            "current_stage": str(run["current_stage"]),
            "workflow_duration_ms": _duration_ms(
                str(run["started_at"]), str(run["completed_at"] or run["updated_at"])
            ),
            "stage_runs": stage_runs,
            "approval_state": approval_state,
            "approval_decision": approval_state if approval_state in {"approved", "rejected"} else None,
            "approval_actor": (action["approved_by"] or action["rejected_by"]) if action else None,
            "approval_reason": action["rejection_reason"] if action else None,
            "llm_enabled": any(bool(row["llm_enabled"]) for row in prompts),
            "providers": _unique_values(prompts, "provider"),
            "models": _unique_values(prompts, "model"),
            "fallback_detected": any(bool(row["fallback_used"]) for row in prompts),
            "fallback_reasons": fallback_reasons,
            "retry_count": int(retries["count"]),
            "tool_event_count": len(tool_events),
            "execution_status": str(execution["status"]) if execution else "not_started",
            "error_classes": list(dict.fromkeys(error_classes)),
            "outcome_label": str(outcome["outcome_label"]) if outcome else None,
            "memory_evidence_count": len(decision.get("memory_evidence_used") or []),
            "memory_influence_summary": decision.get("memory_rationale") or "No memory influence recorded.",
        }

    def _require_demo_run(self, run_id: str) -> dict[str, Any]:
        known_deals = tuple(str(load_scenario(name)["deal"]["deal_id"]) for name in SCENARIO_NAMES)
        placeholders = ",".join("?" for _ in known_deals)
        with self.db.tx() as conn:
            row = conn.execute(
                f"SELECT * FROM workflow_runs WHERE run_id=? AND deal_id IN ({placeholders})",
                (run_id, *known_deals),
            ).fetchone()
        if row is None:
            raise ValueError("Demo workflow run not found")
        return dict(row)
