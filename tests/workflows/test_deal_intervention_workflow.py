from __future__ import annotations

from workflows.deal_intervention_workflow import WORKFLOW_NAME, WORKFLOW_STEPS
from workflows.registry import get_workflow
from workflows.triggers import should_trigger_deal_intervention


def test_deal_intervention_workflow_definition() -> None:
    assert WORKFLOW_NAME == "deal_intervention_workflow"
    assert WORKFLOW_STEPS == [
        "signal_agent",
        "context_agent",
        "strategist_agent",
        "action_agent",
        "execution_agent",
        "evaluator_agent",
    ]


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
