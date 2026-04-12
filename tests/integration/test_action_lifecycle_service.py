from __future__ import annotations

from typing import Any

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


def _start_pending_approval_workflow(monkeypatch, deal_id: str) -> WorkflowAPI:
    payload = _seed_payload(deal_id)
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))
    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    started = api.start_workflow(deal_id, workflow_name="deal_followup_workflow")
    assert started["meta"]["workflow_stage"] == "waiting_approval"
    return api


def test_approve_action_updates_action_and_step_statuses_with_step_scope(reset_db, monkeypatch) -> None:
    deal_id = "deal-approve-step-scope"
    api = _start_pending_approval_workflow(monkeypatch, deal_id)

    action = next(item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id)
    action_id = str(action["action_id"])
    steps_before = api.orchestrator.action_repo.list_action_steps(action_id)
    target_step_id = str(steps_before[0]["step_id"])

    original_resume = api.orchestrator.resume_after_approval
    api.orchestrator.resume_after_approval = lambda envelope, outcome: envelope
    try:
        response = api.approve_action(action_id, approver="qa", step_id=target_step_id)
    finally:
        api.orchestrator.resume_after_approval = original_resume

    assert response == {
        "status": "approved",
        "deal_id": deal_id,
        "action_id": action_id,
        "step_id": target_step_id,
    }

    persisted_action = api.orchestrator.action_repo.get_action(action_id)
    assert persisted_action is not None
    assert persisted_action["status"] == "approved"
    assert persisted_action["approved_by"] == "qa"

    steps_after = api.orchestrator.action_repo.list_action_steps(action_id)
    statuses = {str(step["step_id"]): str(step["status"]) for step in steps_after}
    assert statuses[target_step_id] == "approved"
    for step_id, status in statuses.items():
        if step_id != target_step_id:
            assert status == "pending_approval"


def test_approve_action_resumes_execution_only_for_valid_action(reset_db, monkeypatch) -> None:
    deal_id = "deal-approve-valid"
    api = _start_pending_approval_workflow(monkeypatch, deal_id)

    action = next(item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id)
    action_id = str(action["action_id"])

    response = api.approve_action(action_id, approver="qa")

    assert response["status"] == "approved"
    assert response["deal_id"] == deal_id
    assert response["action_id"] == action_id
    assert response["step_id"] is None

    final_state = api.get_deal_state(deal_id)
    assert final_state["meta"]["workflow_stage"] == "evaluation_done"
    assert final_state["execution_context"]["status"] == "executed"
    assert final_state["outcome_context"]["outcome_label"] in {"positive", "neutral", "negative"}


def test_reject_action_does_not_resume_execution_and_returns_expected_payload(reset_db, monkeypatch) -> None:
    deal_id = "deal-reject-no-resume"
    api = _start_pending_approval_workflow(monkeypatch, deal_id)

    action = next(item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id)
    action_id = str(action["action_id"])
    steps_before = api.orchestrator.action_repo.list_action_steps(action_id)
    target_step_id = str(steps_before[0]["step_id"])

    called = {"resume": 0}
    original_resume = api.orchestrator.resume_after_approval

    def _resume_probe(envelope, outcome):
        called["resume"] += 1
        return original_resume(envelope, outcome)

    api.orchestrator.resume_after_approval = _resume_probe
    response = api.reject_action(action_id, approver="qa", reason="not compliant", step_id=target_step_id)

    assert response == {
        "status": "rejected",
        "deal_id": deal_id,
        "action_id": action_id,
        "step_id": target_step_id,
        "reason": "not compliant",
    }
    assert called["resume"] == 0

    persisted_action = api.orchestrator.action_repo.get_action(action_id)
    assert persisted_action is not None
    assert persisted_action["status"] == "rejected"
    assert persisted_action["rejected_by"] == "qa"
    assert persisted_action["rejection_reason"] == "not compliant"

    steps_after = api.orchestrator.action_repo.list_action_steps(action_id)
    statuses = {str(step["step_id"]): str(step["status"]) for step in steps_after}
    assert statuses[target_step_id] == "rejected"
    for step_id, status in statuses.items():
        if step_id != target_step_id:
            assert status == "pending_approval"

    state = api.get_deal_state(deal_id)
    assert state["execution_context"] is None


def test_edit_action_does_not_resume_execution_and_returns_expected_payload(reset_db, monkeypatch) -> None:
    deal_id = "deal-edit-no-resume"
    api = _start_pending_approval_workflow(monkeypatch, deal_id)

    action = next(item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id)
    action_id = str(action["action_id"])
    steps_before = api.orchestrator.action_repo.list_action_steps(action_id)
    target_step_id = str(steps_before[0]["step_id"])

    called = {"resume": 0}
    original_resume = api.orchestrator.resume_after_approval

    def _resume_probe(envelope, outcome):
        called["resume"] += 1
        return original_resume(envelope, outcome)

    api.orchestrator.resume_after_approval = _resume_probe
    response = api.edit_action(
        action_id,
        approver="qa",
        step_id=target_step_id,
        preview="Updated preview",
        body_draft="Updated body draft",
    )

    assert response == {
        "status": "edited",
        "deal_id": deal_id,
        "action_id": action_id,
        "step_id": target_step_id,
    }
    assert called["resume"] == 0

    persisted_action = api.orchestrator.action_repo.get_action(action_id)
    assert persisted_action is not None
    assert persisted_action["status"] == "pending_approval"
    assert persisted_action["edited_by"] == "qa"
    assert persisted_action["preview"] == "Updated preview"
    assert persisted_action["body_draft"] == "Updated body draft"

    steps_after = api.orchestrator.action_repo.list_action_steps(action_id)
    edited_step = next(step for step in steps_after if str(step["step_id"]) == target_step_id)
    assert edited_step["status"] == "pending_approval"
    assert edited_step["preview"] == "Updated preview"
    assert edited_step["body_draft"] == "Updated body draft"

    state = api.get_deal_state(deal_id)
    assert state["execution_context"] is None
