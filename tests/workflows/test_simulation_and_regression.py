from __future__ import annotations

from typing import Any

import pytest

from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator
from tools import crm_tool
from workflows.registry import get_registered_workflow_names


@pytest.mark.parametrize(
    ("payload", "expected_stage"),
    [
        ({"days_since_reply": 7}, "waiting_approval"),
        ({"days_since_reply": 0, "outbound_count": 0}, "waiting_approval"),
    ],
)
def test_regression_existing_workflows_keep_stage_behavior(reset_db, monkeypatch, payload: dict[str, Any], expected_stage: str) -> None:
    deal_id = "deal-regression-workflow"
    base = {
        "deal_id": deal_id,
        "account": "Acme",
        "contact_name": "Jordan",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "last_touch_summary": "summary",
        "known_objections": [],
    }
    base.update(payload)
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(base))

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    workflow_name = "deal_followup_workflow" if int(base.get("days_since_reply", 0)) >= 5 else "new_deal_outreach_workflow"
    state = api.start_workflow(deal_id, workflow_name=workflow_name)

    assert state["meta"]["workflow_stage"] == expected_stage


def test_regression_existing_endpoint_contracts_remain_stable(reset_db, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from api.app import create_web_app
    from api.router import get_service
    from fastapi.testclient import TestClient

    deal_id = "deal-regression-api"
    payload = {
        "deal_id": deal_id,
        "account": "Acme",
        "contact_name": "Jordan",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 7,
        "last_touch_summary": "summary",
        "known_objections": [],
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    service = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    app = create_web_app()
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as client:
        start = client.post("/api/workflows/start?workflow=deal-followup", json={"deal_id": deal_id})
        assert start.status_code == 200
        assert start.json()["meta"]["workflow_stage"] == "waiting_approval"

        unknown = client.post("/api/workflows/start?workflow=unknown", json={"deal_id": deal_id})
        assert unknown.status_code == 400
        assert unknown.json()["error"] == "unknown_workflow"

        missing_sync = client.get("/api/crm/sync-status")
        assert missing_sync.status_code == 400
        assert missing_sync.json()["error"] == "invalid_request"


def test_simulation_stalled_deal_intervention_needs_approval_then_executes(reset_db, monkeypatch) -> None:
    deal_id = "deal-sim-stalled"
    payload = {
        "deal_id": deal_id,
        "account": "Acme",
        "contact_name": "Jordan",
        "persona": "VP Sales",
        "deal_stage": "negotiation",
        "days_since_reply": 10,
        "deal_stalled": True,
        "risk_score": 92,
        "last_touch_summary": "No reply after legal review.",
        "known_objections": ["security questionnaire"],
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    started = api.start_workflow(deal_id, workflow_name="deal_intervention_workflow")
    assert started["meta"]["workflow_stage"] == "waiting_approval"

    pending = [item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id]
    assert pending

    action_id = str(pending[0]["action_id"])
    _ = api.approve_action(action_id, approver="ops", reply_received=False, meeting_booked=False)
    final_state = api.get_deal_state(deal_id)

    assert final_state["meta"]["workflow_stage"] == "evaluation_done"
    assert final_state["decision_context"]["strategy_type"] in {"risk_mitigation", "risk_reduction", "objection_handling", "nurture"}


def test_simulation_crm_conflict_resolution_and_sync_workflow(reset_db, monkeypatch) -> None:
    crm_tool._DEAL_STORE.clear()
    crm_tool._ACTIVITY_STORE.clear()
    crm_tool._IDEMPOTENCY_CACHE.clear()

    conflict = crm_tool.update_deal_stage(
        deal_id="deal-sim-crm",
        stage="contract_sent",
        idempotency_key="crm-sim-1",
        expected_version=999,
    )
    latest = crm_tool.fetch_deal_record(deal_id="deal-sim-crm")
    resolved = crm_tool.update_deal_stage(
        deal_id="deal-sim-crm",
        stage="contract_sent",
        idempotency_key="crm-sim-2",
        expected_version=int(latest["record"]["version"]),
    )

    assert conflict["success"] is False
    assert conflict["conflict_hints"]["resolution_required"] is True
    assert resolved["success"] is True

    deal_id = "deal-sim-crm-workflow"
    payload = {
        "deal_id": deal_id,
        "account": "Acme",
        "contact_name": "Jordan",
        "persona": "RevOps",
        "deal_stage": "proposal",
        "days_since_reply": 1,
        "last_touch_summary": "post-execution sync",
        "known_objections": [],
        "trigger_event": "post_action_execution",
        "execution_id": "exec-sim-1",
        "crm_sync_required": True,
        "crm_pending_updates": ["execution_result"],
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    state = api.start_workflow(deal_id, workflow_name="crm_sync_workflow")

    assert state["meta"]["workflow_stage"] == "evaluation_done"
    assert state["action_plan"]["steps"][0]["channel"] == "crm"
    assert "crm_sync_workflow" in get_registered_workflow_names()
