from __future__ import annotations

from agents.contracts import ExecutionOutcome
from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator
from workflows.deal_followup_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.triggers import should_trigger_deal_followup


def _followup_payload(*, deal_id: str, days_since_reply: int = 7, budget_objection: bool = True) -> dict:
    objections = ["integration risk"]
    if budget_objection:
        objections.append("budget timing")
    return {
        "deal_id": deal_id,
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": days_since_reply,
        "last_touch_summary": "Shared ROI model and waiting for response.",
        "known_objections": objections,
        "last_updated": "2026-04-12T00:00:00+00:00",
    }


def test_deal_followup_trigger_behavior() -> None:
    assert should_trigger_deal_followup({"days_since_reply": 5}) is True
    assert should_trigger_deal_followup({"days_since_reply": 4}) is False


def test_followup_runner_step_order_and_gated_progression(reset_db, monkeypatch) -> None:
    deal_id = "deal-followup-gated"
    payload = _followup_payload(deal_id=deal_id, budget_objection=True)

    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    orchestrator = WorkflowOrchestrator(approval_threshold=0.8)
    observed_steps: list[str] = []
    original_step_runner = orchestrator._execute_workflow_step

    def wrapped_step_runner(workflow_id: str, step: str, run_deal_id: str, run_id: str, envelope):
        observed_steps.append(step)
        return original_step_runner(workflow_id, step, run_deal_id, run_id, envelope)

    monkeypatch.setattr(orchestrator, "_execute_workflow_step", wrapped_step_runner)
    api = WorkflowAPI(orchestrator=orchestrator)

    started = api.start_workflow(deal_id, workflow_name=WORKFLOW_NAME)

    assert observed_steps == WORKFLOW_STEPS[:4]
    assert started["meta"]["workflow_stage"] == "waiting_approval"
    assert started["action_plan"]["status"] == "pending_approval"
    assert {step["status"] for step in started["action_plan"]["steps"]} == {"pending_approval"}
    assert started["execution_context"] is None
    assert started["outcome_context"] is None

    actions = api.get_actions(status="pending_approval")
    action = next(item for item in actions if item["deal_id"] == deal_id)
    api.approve_action(str(action["action_id"]), approver="pytest")

    finished = api.get_deal_state(deal_id)
    assert finished["meta"]["workflow_stage"] == "evaluation_done"
    assert finished["action_plan"]["status"] == "approved"
    assert {step["status"] for step in finished["action_plan"]["steps"]} == {"executed"}
    assert finished["execution_context"]["status"] == "executed"
    assert finished["outcome_context"]["outcome_label"] in {"positive", "neutral", "negative"}


def test_followup_approved_run_execution_and_evaluation(reset_db, monkeypatch) -> None:
    deal_id = "deal-followup-approved"
    payload = _followup_payload(deal_id=deal_id, budget_objection=False)
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    orchestrator = WorkflowOrchestrator(approval_threshold=0.8)
    envelope = orchestrator.run_workflow(deal_id, workflow_name=WORKFLOW_NAME)

    assert envelope.meta.workflow_stage == "action_done"
    assert envelope.action_plan is not None
    assert envelope.action_plan.status == "approved"
    assert envelope.execution_context is None
    assert envelope.outcome_context is None

    resumed = orchestrator.resume_after_approval(
        envelope,
        ExecutionOutcome(reply_received=False, meeting_booked=False),
    )

    assert resumed.meta.workflow_stage == "evaluation_done"
    assert resumed.execution_context is not None
    assert resumed.execution_context.status == "executed"
    assert resumed.outcome_context is not None
    assert resumed.outcome_context.outcome_label == "neutral"
