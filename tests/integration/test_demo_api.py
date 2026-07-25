from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from api.app import create_web_app
from api.router import get_service
from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator


@pytest.fixture
def demo_client(reset_db, monkeypatch):
    monkeypatch.setenv("MAWI_API_AUTH_MODE", "local-dev-no-auth")
    monkeypatch.setenv("MAWI_API_ENABLE_DEV_MODE", "true")
    monkeypatch.setenv("MAWI_DEMO_MODE", "true")
    service = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    app = create_web_app()
    app.dependency_overrides[get_service] = lambda: service
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.clear()


def test_demo_mode_disabled_returns_clear_error(reset_db, monkeypatch) -> None:
    monkeypatch.delenv("MAWI_DEMO_MODE", raising=False)
    app = create_web_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/api/demo/scenarios")
    assert response.status_code == 403
    assert "Demo API is disabled" in response.json()["detail"]


def test_scenario_listing_has_public_demo_metadata(demo_client) -> None:
    client, _ = demo_client
    response = client.get("/api/demo/scenarios")
    assert response.status_code == 200
    scenarios = response.json()["scenarios"]
    assert len(scenarios) == 3
    assert all(
        set(item)
        == {
            "scenario_id",
            "title",
            "description",
            "expected_workflow",
            "expected_approval_behavior",
            "fallback_demonstrated",
        }
        for item in scenarios
    )
    assert not any("path" in key for item in scenarios for key in item)


def test_unknown_scenario_and_demo_mutation_auth(demo_client, monkeypatch) -> None:
    client, _ = demo_client
    assert client.post("/api/demo/scenarios/unknown/start").status_code == 404

    monkeypatch.setenv("MAWI_API_AUTH_MODE", "protected")
    monkeypatch.setenv("MAWI_API_BEARER_TOKEN", "secret")
    assert client.post("/api/demo/reset").status_code == 401


@pytest.mark.parametrize(
    "scenario_id",
    ["stalled-deal-approval", "rejected-action", "llm-fallback"],
)
def test_start_and_inspect_demo_run(demo_client, scenario_id: str) -> None:
    client, _ = demo_client
    started = client.post(f"/api/demo/scenarios/{scenario_id}/start")
    assert started.status_code == 200
    payload = started.json()
    assert payload["workflow_id"] == "deal_followup_workflow"
    assert payload["current_state"] == "waiting_approval"

    timeline = client.get(f"/api/demo/runs/{payload['run_id']}/timeline").json()["timeline"]
    audit = client.get(f"/api/demo/runs/{payload['run_id']}/audit").json()["audit"]
    telemetry = client.get(f"/api/demo/runs/{payload['run_id']}/telemetry").json()
    assert timeline
    assert [item["timestamp"] for item in timeline] == sorted(item["timestamp"] for item in timeline)
    assert [item["timestamp"] for item in audit] == sorted(item["timestamp"] for item in audit)
    assert all({"stage_name", "status", "timestamp", "summary", "source_agent"} <= set(item) for item in timeline)
    assert telemetry["workflow_id"] == "deal_followup_workflow"
    assert telemetry["current_status"] == "waiting_approval"
    assert telemetry["current_stage"] == "waiting_approval"
    assert telemetry["approval_state"] == "pending_approval"
    assert telemetry["approval_decision"] is None
    assert telemetry["llm_enabled"] is False
    assert telemetry["providers"] == []
    assert telemetry["models"] == []
    assert telemetry["fallback_detected"] is False
    assert telemetry["fallback_reasons"] == []
    assert telemetry["retry_count"] == 0
    assert telemetry["tool_event_count"] == 0
    assert telemetry["execution_status"] == "not_started"
    assert telemetry["error_classes"] == []
    assert telemetry["outcome_label"] is None
    assert telemetry["workflow_duration_ms"] >= 0
    assert telemetry["stage_runs"]
    assert all({"stage", "duration_ms", "status", "error_class"} == set(item) for item in telemetry["stage_runs"])
    assert telemetry["memory_evidence_count"] >= 0
    assert telemetry["memory_influence_summary"]


def test_reset_removes_only_known_demo_records(demo_client, monkeypatch) -> None:
    client, service = demo_client
    client.post("/api/demo/scenarios/rejected-action/start")
    non_demo = {
        "deal_id": "ordinary-deal",
        "account": "Ordinary",
        "contact_name": "Person",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 7,
        "known_objections": ["timing"],
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(non_demo))
    service.start_workflow("ordinary-deal", workflow_name="deal_followup_workflow")

    reset = client.post("/api/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["deleted_demo_runs"] == 1
    assert service.get_deal_state("ordinary-deal")["meta"]["deal_id"] == "ordinary-deal"
    with pytest.raises(ValueError, match="Deal state not found"):
        service.get_deal_state("demo-rejected-northwind-orbit")


def test_non_demo_endpoint_contract_is_unchanged(demo_client, monkeypatch) -> None:
    client, _ = demo_client
    payload = {
        "deal_id": "regression-deal",
        "days_since_reply": 0,
        "known_objections": [],
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))
    response = client.post("/api/workflows/start", json={"deal_id": "regression-deal"})
    assert response.status_code == 200
    assert response.json()["meta"]["deal_id"] == "regression-deal"
