from agents.strategist_agent import strategist_agent
from context.models import DealContext, DecisionContext, SignalContext


def _signal() -> SignalContext:
    return SignalContext(reasoning="seed", confidence=0.8, urgency="high", stalled=True, days_since_reply=9, trigger_reason="seed")


def _deal(*, objections: list[str] | None = None) -> DealContext:
    return DealContext(
        reasoning="seed",
        confidence=0.8,
        persona="vp_sales",
        deal_stage="proposal",
        known_objections=objections or [],
    )


def test_strategist_without_memory_uses_baseline_strategy() -> None:
    result = strategist_agent(_signal(), _deal(objections=["budget timing"]), memory_evidence=[])

    assert isinstance(result, DecisionContext)
    assert result.strategy_type == "roi_framing"
    assert result.memory_evidence_used == []
    assert result.memory_confidence_impact == 0.0
    assert result.confidence == 0.78
    assert "No memory evidence available" in result.memory_rationale


def test_strategist_with_memory_uses_roi_signal_and_caps_confidence_impact() -> None:
    memory = [
        {"snippet": "ROI won in similar proposal cycles", "confidence_impact": 0.2},
        {"snippet": "Risk concerns were secondary", "confidence_impact": 0.1},
        "ignore-me",  # non-dict evidence should be filtered out
    ]

    result = strategist_agent(_signal(), _deal(), memory_evidence=memory)

    assert result.strategy_type == "roi_framing"
    assert result.memory_evidence_used == memory[:2]
    assert result.memory_confidence_impact == 0.15
    assert result.confidence == 0.93
    assert "Used 2 memory evidence item(s)" in result.memory_rationale


def test_strategist_with_risk_memory_picks_risk_reduction() -> None:
    result = strategist_agent(
        _signal(),
        _deal(),
        memory_evidence=[{"snippet": "Risk mitigation narrative converted", "confidence_impact": 0.04}],
    )

    assert result.strategy_type == "risk_reduction"
