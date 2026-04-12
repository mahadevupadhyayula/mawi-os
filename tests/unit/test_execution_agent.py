from agents.execution_agent import execution_agent
from context.models import ActionPlanContext, ActionStep


def _plan(*, status: str = "approved", steps: list[ActionStep] | None = None) -> ActionPlanContext:
    return ActionPlanContext(
        plan_id="plan-1",
        steps=steps or [],
        status=status,
        reasoning="seed",
        confidence=0.8,
    )


def test_execution_agent_fails_when_action_plan_not_approved(monkeypatch) -> None:
    monkeypatch.setattr("agents.execution_agent.uuid4", lambda: "exec-failed")

    result = execution_agent(_plan(status="draft"), deal_id="deal-1", contact_name="Avery")

    assert result.execution_id == "exec-failed"
    assert result.status == "failed"
    assert result.email_result["error"] == "action_plan_not_approved"


def test_execution_agent_status_transitions_partial_and_failed(monkeypatch) -> None:
    monkeypatch.setattr("agents.execution_agent.uuid4", lambda: "exec-1")

    success_step = ActionStep(step_id="s1", order=1, channel="email", action_type="send_email", body_draft="ok", status="approved")
    fail_step = ActionStep(step_id="s2", order=2, channel="crm", action_type="update_crm", body_draft="bad", status="approved")

    def fake_execute(step, *, deal_id: str, contact_name: str):
        return {"success": step.step_id == "s1", "error": "boom" if step.step_id == "s2" else ""}

    monkeypatch.setattr("agents.execution_agent._execute_step", fake_execute)

    partial = execution_agent(_plan(steps=[success_step, fail_step]), deal_id="deal-1", contact_name="Avery")
    assert partial.status == "partial"
    assert success_step.status == "executed"
    assert fail_step.status == "failed"

    fail_step_only = ActionStep(step_id="s3", order=1, channel="email", action_type="send_email", body_draft="bad", status="approved")
    monkeypatch.setattr(
        "agents.execution_agent._execute_step",
        lambda step, *, deal_id, contact_name: {"success": False, "error": "boom"},
    )
    failed = execution_agent(_plan(steps=[fail_step_only]), deal_id="deal-1", contact_name="Avery")
    assert failed.status == "failed"


def test_execution_agent_keeps_already_executed_step_without_retry_increment(monkeypatch) -> None:
    monkeypatch.setattr("agents.execution_agent.uuid4", lambda: "exec-2")

    already = ActionStep(
        step_id="s1",
        order=1,
        channel="email",
        action_type="send_email",
        body_draft="seed",
        status="executed",
        retry_count=2,
        execution_result={"success": True, "message_id": "m1"},
    )

    blocked = ActionStep(step_id="s2", order=2, channel="sms", action_type="send_sms", body_draft="hello", status="approved")

    result = execution_agent(
        _plan(steps=[already, blocked]),
        deal_id="deal-1",
        contact_name="Avery",
        allowed_channels=("email",),
        max_risk_tier="high",
    )

    assert already.retry_count == 2
    assert already.status == "executed"
    assert blocked.status == "failed"
    assert blocked.last_error == "channel_not_allowed"
    assert result.status == "partial"
