from __future__ import annotations

from typing import Any

from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator


def _payload(deal_id: str) -> dict[str, Any]:
    return {
        "deal_id": deal_id,
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 8,
        "last_touch_summary": "Waiting for legal review.",
        "known_objections": ["integration risk"],
        "last_updated": "2026-04-12T00:00:00+00:00",
    }


def test_workflow_lifecycle_trigger_to_persistence(reset_db, monkeypatch) -> None:
    deal_id = "deal-lifecycle-001"
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(_payload(deal_id)))

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))

    started = api.start_workflow(deal_id, workflow_name="deal_followup_workflow")
    assert started["meta"]["workflow_stage"] == "waiting_approval"
    assert started["action_plan"]["status"] == "pending_approval"

    pending = [item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id]
    assert len(pending) == 1
    action_id = str(pending[0]["action_id"])

    approved = api.approve_action(action_id, approver="pytest", reply_received=True, meeting_booked=False)
    assert approved["status"] == "approved"

    final_state = api.get_deal_state(deal_id)
    assert final_state["meta"]["workflow_stage"] == "evaluation_done"
    assert final_state["execution_context"]["status"] == "executed"
    assert final_state["outcome_context"]["outcome_label"] in {"positive", "neutral", "negative"}

    summary = api.get_run_summary(deal_id=deal_id)
    assert summary["run_status"] == "completed"
    assert summary["latest_execution"]["status"] == "executed"
    assert summary["latest_outcome"]["outcome_label"] == final_state["outcome_context"]["outcome_label"]

    persisted = api.orchestrator.workflow_repo.get_latest_envelope(deal_id)
    assert persisted is not None
    assert persisted["meta"]["workflow_stage"] == "evaluation_done"
