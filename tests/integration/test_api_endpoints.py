from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")

from agents.llm_client import LLMResult
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
    monkeypatch.setenv("MAWI_API_AUTH_MODE", "local-dev-no-auth")
    monkeypatch.setenv("MAWI_API_ENABLE_DEV_MODE", "true")
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
    assert "feedback_metrics" in by_deal_payload
    assert "adaptation_blocked_quality" in by_deal_payload["feedback_metrics"]

    by_run = client.get("/api/runs/summary", params={"run_id": run_id})
    assert by_run.status_code == 200
    by_run_payload = by_run.json()
    assert by_run_payload["run_id"] == run_id
    assert by_run_payload["deal_id"] == "deal-api-001"
    assert "feedback_metrics" in by_run_payload
    assert "adaptation_blocked_quality" in by_run_payload["feedback_metrics"]

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


def test_intervention_and_crm_sync_routes_and_sync_status(api_client_and_service, monkeypatch) -> None:
    client, service = api_client_and_service
    payload = _seed_payload("deal-api-sync-001")
    payload.update(
        {
            "deal_stalled": True,
            "trigger_event": "post_action_execution",
            "execution_id": "exec-api-sync-1",
            "crm_sync_required": True,
            "crm_pending_updates": ["execution_result"],
        }
    )
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    intervention_response = client.post("/api/workflows/intervention/run", json={"deal_id": "deal-api-sync-001"})
    assert intervention_response.status_code == 200
    intervention_payload = intervention_response.json()
    assert intervention_payload["status"] == "started"
    assert intervention_payload["workflow_id"] == "deal_intervention_workflow"

    crm_sync_response = client.post("/api/workflows/crm-sync/run", json={"deal_id": "deal-api-sync-001"})
    assert crm_sync_response.status_code == 200
    crm_sync_payload = crm_sync_response.json()
    assert crm_sync_payload["status"] == "started"
    assert crm_sync_payload["workflow_id"] == "crm_sync_workflow"

    run_id = service.orchestrator.workflow_repo.get_latest_run_id("deal-api-sync-001")
    assert run_id is not None

    status_by_deal = client.get("/api/crm/sync-status", params={"deal_id": "deal-api-sync-001"})
    assert status_by_deal.status_code == 200
    status_payload = status_by_deal.json()
    assert status_payload["status"] == "ok"
    assert status_payload["sync_status"] == "completed"

    status_by_run = client.get("/api/crm/sync-status", params={"run_id": run_id})
    assert status_by_run.status_code == 200
    by_run_payload = status_by_run.json()
    assert by_run_payload["run_id"] == run_id
    assert by_run_payload["sync_status"] == "completed"

    missing_params = client.get("/api/crm/sync-status")
    assert missing_params.status_code == 400
    assert missing_params.json()["error"] == "invalid_request"


def test_start_workflow_contract_unchanged_with_llm_explicitly_disabled(api_client_and_service, monkeypatch) -> None:
    monkeypatch.setenv("MAWI_LLM_ENABLED", "false")
    client, _ = api_client_and_service
    response = client.post("/api/workflows/start?workflow=deal-followup", json={"deal_id": "deal-api-001"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["deal_id"] == "deal-api-001"
    assert payload["meta"]["workflow_stage"] == "waiting_approval"
    assert payload["signal_context"]["meta"]["agent"] == "signal_agent"
    assert payload["deal_context"]["meta"]["agent"] == "context_agent"
    assert payload["decision_context"]["meta"]["agent"] == "strategist_agent"
    assert payload["action_context"]["meta"]["agent"] == "action_agent"


def test_start_workflow_llm_enabled_happy_path_with_mocked_client(api_client_and_service, monkeypatch) -> None:
    monkeypatch.setenv("MAWI_LLM_ENABLED", "true")

    def _mock_generate_json(request):
        required = set(request.required_fields)
        payload_by_fields: dict[frozenset[str], dict[str, Any]] = {
            frozenset({"stalled", "days_since_reply", "urgency", "trigger_reason", "reasoning", "confidence"}): {
                "stalled": True,
                "days_since_reply": 9,
                "urgency": "high",
                "trigger_reason": "no_reply_5_days",
                "reasoning": "LLM signal",
                "confidence": 0.94,
            },
            frozenset({"persona", "deal_stage", "known_objections", "recent_timeline", "recommended_tone", "reasoning", "confidence"}): {
                "persona": "RevOps",
                "deal_stage": "proposal",
                "known_objections": ["security review"],
                "recent_timeline": ["LLM timeline"],
                "recommended_tone": "consultative",
                "reasoning": "LLM context",
                "confidence": 0.9,
            },
            frozenset({"strategy_id", "strategy_type", "message_goal", "fallback_strategy", "memory_evidence_used", "memory_confidence_impact", "memory_rationale", "reasoning", "confidence"}): {
                "strategy_id": "strat-roi_framing",
                "strategy_type": "roi_framing",
                "message_goal": "restart_conversation",
                "fallback_strategy": "social_proof",
                "memory_evidence_used": [],
                "memory_confidence_impact": 0.0,
                "memory_rationale": "none",
                "reasoning": "LLM strategy",
                "confidence": 0.88,
            },
            frozenset({"plan_id", "steps", "status", "reasoning", "confidence"}): {
                "plan_id": "plan-llm-1",
                "steps": [],
                "status": "draft",
                "reasoning": "LLM action plan",
                "confidence": 0.86,
            },
        }
        payload = payload_by_fields[frozenset(required)]
        return LLMResult(
            raw_text=str(payload),
            payload=payload,
            latency_ms=15,
            provider="openai",
            model="gpt-4.1-mini",
            error=None,
            token_usage={"total_tokens": 111},
        )

    monkeypatch.setattr("agents.llm_client.generate_json", _mock_generate_json)
    client, _ = api_client_and_service

    response = client.post("/api/workflows/start?workflow=deal-followup", json={"deal_id": "deal-api-001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["workflow_stage"] == "waiting_approval"
    assert payload["deal_context"]["persona"] == "RevOps"
    assert payload["signal_context"]["urgency"] == "high"


def test_mutation_auth_requires_bearer_token_when_protected(reset_db, monkeypatch) -> None:
    monkeypatch.setenv("MAWI_API_AUTH_MODE", "protected")
    monkeypatch.setenv("MAWI_API_BEARER_TOKEN", "secret-token")
    deal_payload = _seed_payload("deal-api-001")
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(deal_payload))

    service = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    app = create_web_app()
    app.dependency_overrides[get_service] = lambda: service
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        missing = client.post("/api/workflows/start", json={"deal_id": "deal-api-001"})
        assert missing.status_code == 401

        bad = client.post(
            "/api/workflows/start",
            json={"deal_id": "deal-api-001"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert bad.status_code == 401

        ok = client.post(
            "/api/workflows/start",
            json={"deal_id": "deal-api-001"},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert ok.status_code == 200

    app.dependency_overrides.clear()
