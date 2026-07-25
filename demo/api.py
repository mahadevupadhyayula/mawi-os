"""Demo-only controls built on the existing workflow API and persistence layer."""

from __future__ import annotations

import json
from typing import Any

from api.service import WorkflowAPI
from demo.scenarios import SCENARIO_NAMES, load_scenario, load_scenarios


_SCENARIO_TITLES = {
    "stalled-deal-approval": "Stalled deal approval",
    "rejected-action": "Rejected follow-up action",
    "llm-fallback": "Deterministic LLM fallback",
}


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
                "SELECT status FROM actions WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)
            ).fetchone()
            prompt = conn.execute(
                """
                SELECT MAX(COALESCE(llm_enabled, 0)) AS llm_enabled,
                       MAX(CASE WHEN fallback_reason IS NOT NULL AND fallback_reason != 'llm_disabled' THEN 1 ELSE 0 END) AS fallback
                FROM prompt_runs WHERE run_id=?
                """,
                (run_id,),
            ).fetchone()
            retries = conn.execute(
                "SELECT COALESCE(SUM(retry_count), 0) AS count FROM action_steps WHERE run_id=?", (run_id,)
            ).fetchone()
            execution = conn.execute(
                "SELECT tool_events_json FROM execution_logs WHERE run_id=? ORDER BY executed_at DESC LIMIT 1", (run_id,)
            ).fetchone()
            outcome = conn.execute(
                "SELECT outcome_label FROM outcomes WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)
            ).fetchone()
        tool_events = json.loads(execution["tool_events_json"]) if execution else []
        return {
            "workflow_id": str(run["workflow_name"]),
            "current_status": str(run["run_status"]),
            "current_stage": str(run["current_stage"]),
            "approval_state": str(action["status"]) if action else "not_required",
            "llm_enabled": bool(prompt["llm_enabled"]) if prompt else False,
            "fallback_detected": bool(prompt["fallback"]) if prompt else False,
            "retry_count": int(retries["count"]),
            "tool_event_count": len(tool_events),
            "outcome_label": str(outcome["outcome_label"]) if outcome else None,
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
