from __future__ import annotations

from typing import Any, Callable

import pytest

from agents.execution_agent import execution_agent
from api.service import WorkflowAPI
from context.models import ActionPlanContext, ActionStep
from orchestrator.runner import WorkflowOrchestrator
from workflows.deal_followup_workflow import WORKFLOW_NAME as FOLLOWUP_WORKFLOW
from workflows.new_deal_outreach_workflow import WORKFLOW_NAME as NEW_DEAL_WORKFLOW


@pytest.fixture
def deal_variant_factory() -> Callable[..., dict[str, Any]]:
    def _build(
        *,
        deal_id: str,
        days_since_reply: int,
        outbound_count: int = 1,
        known_objections: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "deal_id": deal_id,
            "account": "Scenario Corp",
            "contact_name": "Casey Kim",
            "persona": "VP Sales",
            "deal_stage": "proposal",
            "days_since_reply": days_since_reply,
            "last_touch_summary": "Shared a draft mutual action plan.",
            "known_objections": known_objections or ["budget timing"],
            "last_updated": "2026-04-12T00:00:00+00:00",
            "outbound_count": outbound_count,
            "has_prior_outbound": outbound_count > 0,
        }

    return _build


@pytest.fixture
def deterministic_deal_fetch(monkeypatch) -> Callable[[str, dict[str, Any]], None]:
    payloads: dict[str, dict[str, Any]] = {}

    def _set_payload(deal_id: str, payload: dict[str, Any]) -> None:
        payloads[deal_id] = dict(payload)

    def _fetch(deal_id: str) -> dict[str, Any]:
        if deal_id not in payloads:
            raise AssertionError(f"Missing deterministic payload for deal_id={deal_id}")
        return dict(payloads[deal_id])

    monkeypatch.setattr("tools.deal_tool.fetch_deal_data", _fetch)
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", _fetch)
    return _set_payload


def test_scenario_no_reply_followup_triggered(reset_db, deal_variant_factory, deterministic_deal_fetch) -> None:
    deal_id = "scenario-no-reply-followup"
    deterministic_deal_fetch(deal_id, deal_variant_factory(deal_id=deal_id, days_since_reply=6, outbound_count=2))

    state = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99)).start_workflow(
        deal_id,
        workflow_name=FOLLOWUP_WORKFLOW,
    )

    assert state["meta"]["workflow_stage"] == "waiting_approval"
    assert state["action_plan"]["status"] == "pending_approval"


def test_scenario_new_deal_outreach_triggered(reset_db, deal_variant_factory, deterministic_deal_fetch) -> None:
    deal_id = "scenario-new-deal-outreach"
    deterministic_deal_fetch(deal_id, deal_variant_factory(deal_id=deal_id, days_since_reply=0, outbound_count=0))

    state = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99)).start_workflow(
        deal_id,
        workflow_name=NEW_DEAL_WORKFLOW,
    )

    assert state["meta"]["workflow_stage"] == "waiting_approval"
    assert state["action_plan"]["status"] == "pending_approval"


def test_scenario_no_trigger_when_days_below_threshold(reset_db, deal_variant_factory, deterministic_deal_fetch) -> None:
    deal_id = "scenario-no-trigger"
    deterministic_deal_fetch(deal_id, deal_variant_factory(deal_id=deal_id, days_since_reply=4, outbound_count=2))

    state = WorkflowAPI(orchestrator=WorkflowOrchestrator()).start_workflow(deal_id, workflow_name=FOLLOWUP_WORKFLOW)

    assert state["meta"]["workflow_stage"] == "initialized"
    assert state["action_plan"] is None
    assert state["execution_context"] is None


def test_scenario_low_confidence_routes_to_pending_approval(reset_db, deal_variant_factory, deterministic_deal_fetch) -> None:
    deal_id = "scenario-low-confidence"
    deterministic_deal_fetch(deal_id, deal_variant_factory(deal_id=deal_id, days_since_reply=7, outbound_count=1))

    state = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99)).start_workflow(
        deal_id,
        workflow_name=FOLLOWUP_WORKFLOW,
    )

    assert state["action_plan"]["status"] == "pending_approval"
    assert {step["status"] for step in state["action_plan"]["steps"]} == {"pending_approval"}


def test_scenario_rejected_action_halts_without_execution() -> None:
    plan = ActionPlanContext(reasoning="seed", confidence=0.7, status="rejected", plan_id="plan-rejected")
    plan.steps = [
        ActionStep(
            step_id="s-rejected",
            order=1,
            channel="email",
            action_type="send_email",
            subject="Checking in",
            body_draft="Wanted to follow up.",
            status="rejected",
        )
    ]

    execution = execution_agent(plan, deal_id="deal-rejected", contact_name="Casey")

    assert execution.status == "failed"
    assert execution.tool_events == []
    assert execution.email_result["error"] == "action_plan_not_approved"


def test_scenario_policy_violating_content_blocked_with_escalation_metadata() -> None:
    plan = ActionPlanContext(reasoning="seed", confidence=0.9, status="approved", plan_id="plan-policy")
    step = ActionStep(
        step_id="s-policy",
        order=1,
        channel="email",
        action_type="send_email",
        subject="Guaranteed response",
        body_draft="We guarantee a 100% response and never fail.",
        status="approved",
    )
    plan.steps = [step]

    execution = execution_agent(plan, deal_id="deal-policy", contact_name="Casey")
    blocking_event = next(event for event in execution.tool_events if event.get("event_type") == "blocked_by_output_policy")

    assert execution.status == "failed"
    assert step.last_error == "generated_output_policy_violation"
    assert "prohibited_claim_detected" in blocking_event["policy_reasons"]
    assert blocking_event["escalation"]


def test_scenario_successful_execution_records_tool_events_logs_and_outcome(
    reset_db,
    deal_variant_factory,
    deterministic_deal_fetch,
) -> None:
    deal_id = "scenario-success"
    deterministic_deal_fetch(
        deal_id,
        deal_variant_factory(
            deal_id=deal_id,
            days_since_reply=7,
            outbound_count=1,
            known_objections=["integration risk"],
        ),
    )

    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99))
    api.start_workflow(deal_id, workflow_name=FOLLOWUP_WORKFLOW)
    action = next(item for item in api.get_actions(status="pending_approval") if item["deal_id"] == deal_id)
    api.approve_action(str(action["action_id"]), approver="pytest", reply_received=True)

    finished = api.get_deal_state(deal_id)
    tool_events = finished["execution_context"]["tool_events"]
    by_step_event = next(event for event in tool_events if "by_step" in event)

    assert finished["meta"]["workflow_stage"] == "evaluation_done"
    assert finished["execution_context"]["status"] == "executed"
    assert any(event.get("event_type") == "executed" for event in tool_events if "event_type" in event)
    assert by_step_event["by_step"]
    assert finished["outcome_context"]["outcome_label"] in {"positive", "neutral", "negative"}
