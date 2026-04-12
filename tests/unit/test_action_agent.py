from agents.action_agent import action_agent
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
