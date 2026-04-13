from __future__ import annotations

import json

from agents.crm_agent import crm_agent
from agents.inference import ModelResolution
from agents.prompt_templates import PromptLintError
from context.models import DealContext


def _deal_context() -> DealContext:
    return DealContext(
        persona="RevOps",
        deal_stage="proposal",
        known_objections=[],
        recent_timeline=["Demo complete"],
        recommended_tone="consultative",
        reasoning="seed",
        confidence=0.8,
    )


def test_crm_agent_builds_strict_crm_plan_from_normalized_state() -> None:
    raw_data = {
        "crm_state": {
            "record_id": "crm-123",
            "sync_required": True,
            "pending_updates": ["last_email_summary", "next_step_date"],
        },
        "trigger_event": "post_action_execution",
    }

    result = crm_agent(raw_data, _deal_context())

    assert result.status == "approved"
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.channel == "crm"
    assert step.action_type == "update_crm"
    assert step.status == "approved"
    assert "record_id=crm-123" in step.body_draft
    assert 0.0 <= result.confidence <= 1.0


def test_crm_agent_uses_llm_payload_steps_when_not_fallback(monkeypatch) -> None:
    payload = {
        "plan_id": "crm-llm-plan",
        "steps": [
            {
                "step_id": "crm-step-2",
                "order": 2,
                "channel": "crm",
                "action_type": "update_crm",
                "preview": "second",
                "body_draft": "second body",
                "status": "approved",
            },
            {
                "step_id": "crm-step-1",
                "order": 1,
                "channel": "email",
                "action_type": "send_email",
                "subject": "llm email first",
                "status": "draft",
            },
        ],
        "status": "approved",
        "reasoning": "llm crm reasoning",
        "confidence": 0.77,
    }
    monkeypatch.setattr(
        "agents.crm_agent.resolve_model_output",
        lambda **_: ModelResolution(
            model_output=json.dumps(payload),
            llm_enabled=True,
            provider="openai",
            model="gpt-test",
        ),
    )

    result = crm_agent({"crm_state": {"record_id": "crm-123"}}, _deal_context())

    assert [step.step_id for step in result.steps] == ["crm-step-1", "crm-step-2"]
    assert result.steps[0].subject == "llm email first"
    assert result.steps[1].preview == "second"


def test_crm_agent_raises_prompt_lint_error_on_malformed_llm_step(monkeypatch) -> None:
    payload = {
        "plan_id": "crm-llm-plan",
        "steps": [{"step_id": "only-id", "order": 1, "channel": "crm"}],
        "status": "approved",
        "reasoning": "llm crm reasoning",
        "confidence": 0.77,
    }
    monkeypatch.setattr(
        "agents.crm_agent.resolve_model_output",
        lambda **_: ModelResolution(
            model_output=json.dumps(payload),
            llm_enabled=True,
            provider="openai",
            model="gpt-test",
        ),
    )

    try:
        crm_agent({"crm_state": {"record_id": "crm-123"}}, _deal_context())
    except PromptLintError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("Expected PromptLintError")
