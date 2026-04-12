from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")

from api.app import create_web_app
from api.router import get_service
from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator


def _seed_payload(deal_id: str) -> dict[str, Any]:
    return {
        "deal_id": deal_id,
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 7,
        "last_touch_summary": "Shared ROI model and waiting for response.",
        "known_objections": ["budget timing", "integration risk"],
        "last_updated": "2026-04-12T00:00:00+00:00",
    }


@pytest.fixture
def api_client_and_service(reset_db, monkeypatch):
    deal_payload = _seed_payload("deal-api-001")
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(deal_payload))

    service = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    app = create_web_app()
    app.dependency_overrides[get_service] = lambda: service
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.clear()


def test_start_workflow_happy_path_and_unknown_workflow_error(api_client_and_service) -> None:
    client, _ = api_client_and_service

    response = client.post("/api/workflows/start?workflow=deal-followup", json={"deal_id": "deal-api-001"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["deal_id"] == "deal-api-001"
    assert payload["meta"]["workflow_stage"] == "waiting_approval"

    error_response = client.post("/api/workflows/start?workflow=not-a-workflow", json={"deal_id": "deal-api-001"})

    assert error_response.status_code == 400
    assert error_response.json()["error"] == "unknown_workflow"


def test_actions_route_happy_path_and_not_found_for_mutations(api_client_and_service) -> None:
    client, _ = api_client_and_service
    client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})

    actions_response = client.get("/api/actions", params={"status": "pending_approval"})
    assert actions_response.status_code == 200
    actions = actions_response.json()["actions"]
    assert actions

    missing_approve = client.post(
        "/api/actions/approve",
        json={"workflow": "deal-followup", "action_id": "missing-action", "approver": "qa"},
    )
    assert missing_approve.status_code == 404
    assert missing_approve.json()["error"] == "action_not_found"

    missing_reject = client.post(
        "/api/actions/reject",
        json={"workflow": "deal-followup", "action_id": "missing-action", "approver": "qa", "reason": "invalid"},
    )
    assert missing_reject.status_code == 404
    assert missing_reject.json()["error"] == "action_not_found"

    missing_edit = client.post(
        "/api/actions/edit",
        json={"workflow": "deal-followup", "action_id": "missing-action", "approver": "qa", "preview": "x"},
    )
    assert missing_edit.status_code == 404
    assert missing_edit.json()["error"] == "action_not_found"


def test_action_mutations_happy_path_and_unknown_workflow_error(api_client_and_service) -> None:
    client, _ = api_client_and_service

    client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})
    actions = client.get("/api/actions", params={"status": "pending_approval"}).json()["actions"]
    action_id = str(actions[0]["action_id"])

    approve = client.post(
        "/api/actions/approve",
        json={"workflow": "deal-followup", "action_id": action_id, "approver": "qa"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    unknown_workflow = client.post(
        "/api/actions/approve",
        json={"workflow": "not-a-workflow", "action_id": action_id, "approver": "qa"},
    )
    assert unknown_workflow.status_code == 400
    assert unknown_workflow.json()["error"] == "unknown_workflow"

    client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})
    action_id_2 = client.get("/api/actions", params={"status": "pending_approval"}).json()["actions"][0]["action_id"]

    reject = client.post(
        "/api/actions/reject",
        json={"workflow": "deal-followup", "action_id": action_id_2, "approver": "qa", "reason": "needs revision"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    edit = client.post(
        "/api/actions/edit",
        json={
            "workflow": "deal-followup",
            "action_id": action_id_2,
            "approver": "qa",
            "preview": "Updated preview",
            "body_draft": "Updated body",
        },
    )
    assert edit.status_code == 200
    assert edit.json()["status"] == "edited"


def test_get_deal_state_serialized_envelope_and_not_found(api_client_and_service) -> None:
    client, _ = api_client_and_service

    client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})
    response = client.get("/api/deals/deal-api-001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["deal_id"] == "deal-api-001"
    assert payload["meta"]["workflow_stage"] in {"waiting_approval", "evaluation_done"}
    assert payload["signal_context"]["meta"]["agent"] == "signal_agent"
    assert payload["deal_context"]["meta"]["agent"] == "context_agent"
    assert payload["decision_context"]["meta"]["agent"] == "strategist_agent"
    assert payload["action_context"]["meta"]["agent"] == "action_agent"
    assert "history" in payload
    assert isinstance(payload["raw_data"], dict)

    missing = client.get("/api/deals/deal-does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"] == "deal_state_not_found"


def test_get_run_summary_by_deal_id_and_run_id_and_not_found(api_client_and_service) -> None:
    client, service = api_client_and_service

    client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})
    run_id = service.orchestrator.workflow_repo.get_latest_run_id("deal-api-001")
    assert run_id is not None

    by_deal = client.get("/api/runs/summary", params={"deal_id": "deal-api-001"})
    assert by_deal.status_code == 200
    by_deal_payload = by_deal.json()
    assert by_deal_payload["deal_id"] == "deal-api-001"
    assert by_deal_payload["run_id"] == run_id
    assert "path_metrics" in by_deal_payload

    by_run = client.get("/api/runs/summary", params={"run_id": run_id})
    assert by_run.status_code == 200
    by_run_payload = by_run.json()
    assert by_run_payload["run_id"] == run_id
    assert by_run_payload["deal_id"] == "deal-api-001"

    missing = client.get("/api/runs/summary", params={"run_id": "missing-run"})
    assert missing.status_code == 404
    assert missing.json()["error"] == "run_summary_not_found"


def test_start_crm_sync_workflow_via_alias_runs_to_evaluation(api_client_and_service, monkeypatch) -> None:
    client, _ = api_client_and_service
    payload = _seed_payload("deal-api-crm-001")
    payload.update(
        {
            "trigger_event": "post_action_execution",
            "execution_id": "exec-api-1",
            "crm_sync_required": True,
            "crm_pending_updates": ["execution_result"],
        }
    )
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    response = client.post("/api/workflows/start?workflow=crm-sync", json={"deal_id": "deal-api-crm-001"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["workflow_stage"] == "evaluation_done"
    assert data["action_plan"]["steps"][0]["channel"] == "crm"
