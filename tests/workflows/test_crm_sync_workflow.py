from __future__ import annotations

from agents.contracts import ExecutionOutcome
from orchestrator.runner import WorkflowOrchestrator
from workflows.crm_sync_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.registry import get_workflow
from workflows.triggers import should_trigger_crm_sync


def test_crm_sync_workflow_definition() -> None:
    assert WORKFLOW_NAME == "crm_sync_workflow"
    assert WORKFLOW_STEPS == [
        "signal_agent",
        "context_agent",
        "crm_agent",
        "execution_agent",
        "evaluator_agent",
    ]


def test_crm_sync_trigger_behavior() -> None:
    assert should_trigger_crm_sync({"trigger_source": "api", "trigger_event": "explicit", "crm_sync_required": True}) is True
    assert should_trigger_crm_sync({"trigger_event": "post_action_execution", "execution_id": "exec-1"}) is True
    assert should_trigger_crm_sync({"days_since_reply": 7}) is False


def test_crm_sync_registry_configuration() -> None:
    workflow = get_workflow(WORKFLOW_NAME)

    assert workflow.workflow_id == WORKFLOW_NAME
    assert workflow.steps == WORKFLOW_STEPS
    assert workflow.trigger({"trigger_source": "api", "trigger_event": "explicit", "crm_sync_required": True}) is True
    assert workflow.config["release_version"] == "2026.04.1"


def test_crm_sync_workflow_runs_through_execution_and_evaluation(reset_db, monkeypatch) -> None:
    deal_id = "deal-crm-sync"
    payload = {
        "deal_id": deal_id,
        "contact_name": "Jordan Lee",
        "persona": "RevOps",
        "deal_stage": "proposal",
        "days_since_reply": 1,
        "known_objections": [],
        "last_touch_summary": "Action executed.",
        "trigger_event": "post_action_execution",
        "execution_id": "exec-123",
        "crm_sync_required": True,
        "crm_pending_updates": ["execution_result", "next_step"],
        "reply_received": False,
        "meeting_booked": False,
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))

    orchestrator = WorkflowOrchestrator(approval_threshold=0.99)
    envelope = orchestrator.run_workflow(deal_id, workflow_name=WORKFLOW_NAME)

    assert envelope.meta.workflow_stage == "evaluation_done"
    assert envelope.action_plan is not None
    assert envelope.action_plan.status == "approved"
    assert {step.channel for step in envelope.action_plan.steps} == {"crm"}
    assert envelope.execution_context is not None
    assert envelope.execution_context.status == "executed"
    assert envelope.outcome_context is not None
    assert envelope.outcome_context.outcome_label in {"neutral", "positive", "negative"}

    resumed = orchestrator.resume_after_approval(
        envelope,
        ExecutionOutcome(reply_received=False, meeting_booked=False),
    )
    assert resumed.meta.workflow_stage == "evaluation_done"
