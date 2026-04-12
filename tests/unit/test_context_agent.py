from agents.context_agent import context_agent
from context.models import DealContext, SignalContext


def _signal(*, urgency: str = "low", stalled: bool = False) -> SignalContext:
    return SignalContext(
        reasoning="seed",
        confidence=0.8,
        urgency=urgency,
        stalled=stalled,
        days_since_reply=0,
        trigger_reason="seed",
    )


def test_context_agent_populates_defaults_for_missing_raw_fields() -> None:
    result = context_agent({}, _signal())

    assert isinstance(result, DealContext)
    assert result.persona == "unknown"
    assert result.deal_stage == "unknown"
    assert result.known_objections == []
    assert result.recent_timeline == [""]
    assert result.recommended_tone == "neutral"


def test_context_agent_uses_signal_to_choose_tone_and_confidence() -> None:
    stalled_signal = _signal(urgency="medium", stalled=True)

    result = context_agent(
        {
            "persona": "vp_sales",
            "deal_stage": "proposal",
            "known_objections": [],
            "last_touch_summary": "No reply after pricing note.",
        },
        stalled_signal,
    )

    assert result.recommended_tone == "consultative"
    assert result.confidence == 0.82
    assert result.recent_timeline == ["No reply after pricing note."]


def test_context_agent_handles_empty_objections_list() -> None:
    result = context_agent({"known_objections": []}, _signal())

    assert result.known_objections == []
