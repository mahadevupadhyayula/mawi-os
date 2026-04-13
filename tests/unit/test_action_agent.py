import json

from agents.action_agent import action_agent
from agents.inference import ModelResolution
from agents.prompt_templates import PromptLintError
from context.models import ActionPlanContext, DealContext, DecisionContext


def _deal() -> DealContext:
    return DealContext(reasoning="seed", confidence=0.8, persona="vp_sales", deal_stage="proposal")


def _decision(*, strategy_type: str = "roi_framing", memory_evidence_used=None, memory_confidence_impact: float = 0.0) -> DecisionContext:
    return DecisionContext(
        reasoning="seed",
        confidence=0.8,
        strategy_id=f"strat-{strategy_type}",
        strategy_type=strategy_type,
        message_goal="restart_conversation",
        fallback_strategy="social_proof",
        memory_evidence_used=memory_evidence_used or [],
        memory_confidence_impact=memory_confidence_impact,
        memory_rationale="seed",
    )


def test_action_agent_returns_typed_plan_and_deterministic_ids(monkeypatch) -> None:
    ids = iter(["step-1", "step-2", "plan-1"])
    monkeypatch.setattr("agents.action_agent.uuid4", lambda: next(ids))

    result = action_agent(_decision(memory_evidence_used=[]), _deal())

    assert isinstance(result, ActionPlanContext)
    assert result.plan_id == "plan-1"
    assert [step.step_id for step in result.steps] == ["step-1", "step-2"]
    assert result.status == "draft"


def test_action_agent_branches_subject_and_cta_with_memory_strength() -> None:
    weak = action_agent(
        _decision(memory_evidence_used=[{"snippet": "roi"}], memory_confidence_impact=0.05),
        _deal(),
    )
    strong = action_agent(
        _decision(memory_evidence_used=[{"snippet": "roi"}], memory_confidence_impact=0.08),
        _deal(),
    )

    assert weak.steps[0].subject == "Follow-up: ROI path based on similar deals"
    assert "two concrete next-step options" in weak.steps[0].body_draft
    assert "hold a 15-minute slot this week" in strong.steps[0].body_draft


def test_action_agent_non_roi_strategy_uses_risk_crm_copy() -> None:
    result = action_agent(_decision(strategy_type="risk_reduction"), _deal())

    assert result.steps[1].channel == "crm"
    assert "sequenced follow-up" in result.steps[1].preview


def test_action_agent_uses_llm_payload_steps_when_not_fallback(monkeypatch) -> None:
    payload = {
        "plan_id": "llm-plan",
        "steps": [
            {
                "step_id": "llm-step-2",
                "order": 2,
                "channel": "crm",
                "action_type": "update_crm",
                "preview": "llm crm preview",
                "body_draft": "llm crm body",
                "status": "approved",
            },
            {
                "step_id": "llm-step-1",
                "order": 1,
                "channel": "email",
                "action_type": "send_email",
                "subject": "llm subject",
                "preview": "llm email preview",
                "body_draft": "llm email body",
                "status": "pending_approval",
            },
        ],
        "status": "pending_approval",
        "reasoning": "llm reasoning",
        "confidence": 0.91,
    }
    monkeypatch.setattr(
        "agents.action_agent.resolve_model_output",
        lambda **_: ModelResolution(
            model_output=json.dumps(payload),
            llm_enabled=True,
            provider="openai",
            model="gpt-test",
        ),
    )

    result = action_agent(_decision(memory_evidence_used=[]), _deal())

    assert [step.step_id for step in result.steps] == ["llm-step-1", "llm-step-2"]
    assert result.steps[0].subject == "llm subject"
    assert result.steps[1].preview == "llm crm preview"
    assert result.status == "pending_approval"


def test_action_agent_raises_prompt_lint_error_on_malformed_llm_step(monkeypatch) -> None:
    payload = {
        "plan_id": "llm-plan",
        "steps": [
            {
                "step_id": "llm-step-1",
                "order": 1,
                "action_type": "send_email",
            }
        ],
        "status": "draft",
        "reasoning": "llm reasoning",
        "confidence": 0.5,
    }
    monkeypatch.setattr(
        "agents.action_agent.resolve_model_output",
        lambda **_: ModelResolution(
            model_output=json.dumps(payload),
            llm_enabled=True,
            provider="openai",
            model="gpt-test",
        ),
    )

    try:
        action_agent(_decision(), _deal())
    except PromptLintError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("Expected PromptLintError")
