from __future__ import annotations

import pytest

from orchestrator.runner import WorkflowOrchestrator
from workflows.registry import WorkflowMetadata


def test_orchestrator_rejects_workflow_without_evaluator_stage(reset_db, monkeypatch) -> None:
    payload = {
        "deal_id": "deal-guardrail-missing-evaluator",
        "contact_name": "Jordan Lee",
        "persona": "RevOps",
        "days_since_reply": 7,
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))
    invalid = WorkflowMetadata(
        workflow_id="invalid_missing_evaluator",
        steps=["signal_agent", "context_agent", "action_agent", "execution_agent"],
        trigger=lambda _raw: True,
    )
    monkeypatch.setattr("orchestrator.runner.get_workflow", lambda _name=None: invalid)

    orchestrator = WorkflowOrchestrator()
    with pytest.raises(ValueError, match="must include 'evaluator_agent' stage"):
        orchestrator.run_workflow("deal-guardrail-missing-evaluator", workflow_name="invalid_missing_evaluator")


def test_orchestrator_rejects_workflow_with_evaluator_before_execution(reset_db, monkeypatch) -> None:
    payload = {
        "deal_id": "deal-guardrail-bad-order",
        "contact_name": "Jordan Lee",
        "persona": "RevOps",
        "days_since_reply": 7,
    }
    monkeypatch.setattr("orchestrator.runner.fetch_deal_data", lambda _deal_id: dict(payload))
    invalid = WorkflowMetadata(
        workflow_id="invalid_evaluator_before_execution",
        steps=["signal_agent", "evaluator_agent", "execution_agent"],
        trigger=lambda _raw: True,
    )
    monkeypatch.setattr("orchestrator.runner.get_workflow", lambda _name=None: invalid)

    orchestrator = WorkflowOrchestrator()
    with pytest.raises(ValueError, match="must run before 'evaluator_agent'"):
        orchestrator.run_workflow("deal-guardrail-bad-order", workflow_name="invalid_evaluator_before_execution")
