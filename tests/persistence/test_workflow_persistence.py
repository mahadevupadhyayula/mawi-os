from __future__ import annotations

import json

from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator


def _pending_approval_payload(deal_id: str) -> dict:
    return {
        "deal_id": deal_id,
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 7,
        "last_touch_summary": "Shared ROI model and waiting for response.",
        "known_objections": ["integration risk", "budget timing"],
        "last_updated": "2026-04-12T00:00:00+00:00",
    }


def _run_approval_to_execution(*, deal_id: str, monkeypatch) -> tuple[WorkflowAPI, dict]:
    payload = _pending_approval_payload(deal_id)
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.8))
    started = api.start_workflow(deal_id)
    assert started["meta"]["workflow_stage"] == "waiting_approval"

    actions = api.get_actions(status="pending_approval")
    action = next(item for item in actions if item["deal_id"] == deal_id)
    api.approve_action(str(action["action_id"]), approver="pytest")

    finished = api.get_deal_state(deal_id)
    assert finished["meta"]["workflow_stage"] == "evaluation_done"
    return api, finished


def test_workflow_persists_consistent_rows_across_tables(reset_db, monkeypatch) -> None:
    _ = reset_db
    deal_id = "deal-persistence-rows"
    api, _finished = _run_approval_to_execution(deal_id=deal_id, monkeypatch=monkeypatch)

    repo = api.orchestrator.workflow_repo
    with repo.db.tx() as conn:
        run_row = conn.execute("SELECT * FROM workflow_runs WHERE deal_id=?", (deal_id,)).fetchone()
        assert run_row is not None
        run_id = str(run_row["run_id"])

        action_row = conn.execute("SELECT * FROM actions WHERE run_id=? AND deal_id=?", (run_id, deal_id)).fetchone()
        assert action_row is not None
        action_id = str(action_row["action_id"])

        envelope_rows = conn.execute(
            "SELECT run_id, deal_id FROM context_envelopes WHERE run_id=? AND deal_id=?",
            (run_id, deal_id),
        ).fetchall()
        assert len(envelope_rows) >= 1

        step_rows = conn.execute("SELECT * FROM action_steps WHERE action_id=? ORDER BY step_order", (action_id,)).fetchall()
        assert len(step_rows) >= 1

        execution_row = conn.execute("SELECT * FROM execution_logs WHERE action_id=?", (action_id,)).fetchone()
        assert execution_row is not None
        execution_id = str(execution_row["execution_id"])

        execution_step_rows = conn.execute(
            "SELECT * FROM execution_step_logs WHERE execution_id=? ORDER BY step_order",
            (execution_id,),
        ).fetchall()
        assert len(execution_step_rows) == len(step_rows)

        outcome_row = conn.execute("SELECT * FROM outcomes WHERE action_id=?", (action_id,)).fetchone()
        assert outcome_row is not None

    assert run_row["deal_id"] == deal_id
    assert run_row["run_status"] == "completed"
    assert action_row["run_id"] == run_id
    assert action_row["deal_id"] == deal_id

    for step_row in step_rows:
        assert step_row["run_id"] == run_id
        assert step_row["deal_id"] == deal_id
        assert step_row["action_id"] == action_id

    for execution_step_row in execution_step_rows:
        assert execution_step_row["run_id"] == run_id
        assert execution_step_row["deal_id"] == deal_id
        assert execution_step_row["action_id"] == action_id

    by_step_entries = json.loads(execution_row["tool_events_json"])
    detail_entry = next(item for item in by_step_entries if "by_step" in item)
    assert len(detail_entry["by_step"]) == len(step_rows)
    assert outcome_row["run_id"] == run_id
    assert outcome_row["deal_id"] == deal_id


def test_workflow_repository_get_summary_and_latest_envelope(reset_db, monkeypatch) -> None:
    _ = reset_db
    deal_id = "deal-persistence-summary"
    api, finished = _run_approval_to_execution(deal_id=deal_id, monkeypatch=monkeypatch)

    repo = api.orchestrator.workflow_repo
    summary_by_deal = repo.get_run_summary(deal_id=deal_id)
    assert summary_by_deal is not None

    run_id = str(summary_by_deal["run_id"])
    summary_by_run = repo.get_run_summary(run_id=run_id)
    assert summary_by_run is not None

    assert summary_by_deal["run_id"] == summary_by_run["run_id"]
    assert summary_by_deal["deal_id"] == deal_id
    assert summary_by_deal["run_status"] == "completed"
    assert summary_by_deal["latest_execution"]["status"] in {"executed", "partial", "failed"}
    assert isinstance(summary_by_deal["action_step_status_counts"], dict)
    assert "executed" in summary_by_deal["action_step_status_counts"]
    assert summary_by_deal["latest_outcome"]["outcome_label"] == finished["outcome_context"]["outcome_label"]

    latest_envelope = repo.get_latest_envelope(deal_id)
    assert latest_envelope is not None
    assert latest_envelope["meta"]["deal_id"] == deal_id
    assert latest_envelope["meta"]["workflow_stage"] == "evaluation_done"
    assert latest_envelope["execution_context"]["status"] == finished["execution_context"]["status"]
    assert latest_envelope["outcome_context"]["outcome_label"] == finished["outcome_context"]["outcome_label"]
