from agents.intervention_agent import intervention_agent
from context.models import DealContext, SignalContext



def _signal(*, stalled: bool = True, urgency: str = "high") -> SignalContext:
    return SignalContext(
        stalled=stalled,
        days_since_reply=8,
        urgency=urgency,
        trigger_reason="no_reply_5_days" if stalled else "not_stalled",
        reasoning="seed",
        confidence=0.8,
    )



def _deal(*, objections: list[str] | None = None) -> DealContext:
    return DealContext(
        persona="ops_lead",
        deal_stage="proposal",
        known_objections=objections or [],
        recent_timeline=["follow-up sent"],
        recommended_tone="consultative",
        reasoning="seed",
        confidence=0.8,
    )



def test_intervention_agent_returns_intervene_for_high_risk_signals() -> None:
    result = intervention_agent(_signal(urgency="high"), _deal(objections=["security review pending"]))

    assert result.result == "intervene"
    assert result.reason
    assert 0.0 <= result.confidence <= 1.0



def test_intervention_agent_returns_hold_without_stall_or_risk() -> None:
    result = intervention_agent(_signal(stalled=False, urgency="low"), _deal(objections=["pricing"]))

    assert result.result == "hold"
