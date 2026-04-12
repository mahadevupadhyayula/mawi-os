from __future__ import annotations

from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator
from workflows.deal_intervention_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.registry import get_workflow
from workflows.triggers import should_trigger_deal_intervention


def _intervention_payload(*, deal_id: str, urgency_days: int = 9, objections: list[str] | None = None) -> dict:
    return {
        "deal_id": deal_id,
        "account": "Escalation Labs",
        "contact_name": "Jordan Lee",
        "persona": "RevOps",
        "deal_stage": "proposal",
        "days_since_reply": urgency_days,
        "last_touch_summary": "Security concerns raised in procurement review.",
        "known_objections": objections or ["security review pending"],
        "last_updated": "2026-04-12T00:00:00+00:00",
        "risk_tier": "high",
        "risk_score": 88,
    }


def test_deal_intervention_workflow_definition() -> None:
    assert WORKFLOW_NAME == "deal_intervention_workflow"
    assert WORKFLOW_STEPS == [
        "signal_agent",
        "context_agent",
        "intervention_agent",
        "strategist_agent",
        "action_agent",
        "execution_agent",
        "evaluator_agent",
    ]


def test_deal_intervention_workflow_definition_includes_execution_then_evaluator() -> None:
    assert WORKFLOW_STEPS.index("execution_agent") < WORKFLOW_STEPS.index("evaluator_agent")


def test_deal_intervention_trigger_behavior() -> None:
    assert should_trigger_deal_intervention({"deal_stalled": True}) is True
    assert should_trigger_deal_intervention({"no_reply": True}) is True
    assert should_trigger_deal_intervention({"risk_tier": "high"}) is True
    assert should_trigger_deal_intervention({"risk_score": 90}) is True
    assert should_trigger_deal_intervention({"risk_score": 70}) is True
    assert should_trigger_deal_intervention({"risk_score": 69}) is False


def test_deal_intervention_registry_configuration() -> None:
    workflow = get_workflow(WORKFLOW_NAME)

    assert workflow.workflow_id == WORKFLOW_NAME
    assert workflow.steps == WORKFLOW_STEPS
    assert workflow.trigger({"risk_tier": "critical"}) is True
    assert workflow.config["release_version"] == "2026.04.1"
    assert workflow.config["max_risk_tier_by_phase"] == {
        "default": "critical",
        "autonomous": "medium",
        "human_review": "critical",
    }


def test_deal_intervention_runner_executes_intervention_stage(reset_db, monkeypatch) -> None:
    deal_id = "deal-intervention-gated"
    payload = _intervention_payload(deal_id=deal_id)
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

    assert observed_steps == WORKFLOW_STEPS[:5]
    assert started["intervention_decision_context"] is not None
    assert started["intervention_decision_context"]["result"] == "intervene"
    assert started["intervention_decision_context"]["meta"]["source_agent"] == "intervention_agent"
    assert started["action_plan"]["status"] in {"approved", "pending_approval"}
