from agents.context_agent import context_agent
from agents.llm_client import LLMResult
from context.models import DealContext, SignalContext
import pytest


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


def test_context_agent_llm_enabled_hydrates_dataclass_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAWI_LLM_ENABLED", "true")

    def _mock_generate_json(_request):
        return LLMResult(
            raw_text='{"persona":"CTO","deal_stage":"evaluation","known_objections":["security"],"recent_timeline":["Asked for architecture doc"],"recommended_tone":"technical","reasoning":"LLM-generated context","confidence":0.91}',
            payload={
                "persona": "CTO",
                "deal_stage": "evaluation",
                "known_objections": ["security"],
                "recent_timeline": ["Asked for architecture doc"],
                "recommended_tone": "technical",
                "reasoning": "LLM-generated context",
                "confidence": 0.91,
            },
            latency_ms=12,
            provider="openai",
            model="gpt-4.1-mini",
            error=None,
            token_usage={"total_tokens": 42},
        )

    monkeypatch.setattr("agents.llm_client.generate_json", _mock_generate_json)

    result = context_agent({"persona": "VP Sales", "deal_stage": "proposal"}, _signal(urgency="medium", stalled=True))

    assert isinstance(result, DealContext)
    assert result.persona == "CTO"
    assert result.deal_stage == "evaluation"
    assert result.known_objections == ["security"]
    assert result.recent_timeline == ["Asked for architecture doc"]
    assert result.recommended_tone == "technical"
    assert result.reasoning == "LLM-generated context"
    assert result.confidence == 0.91


@pytest.mark.parametrize("error_code", ["invalid_json", "provider_error"])
def test_context_agent_llm_errors_fall_back_to_deterministic_output(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
) -> None:
    monkeypatch.setenv("MAWI_LLM_ENABLED", "true")

    def _mock_generate_json(_request):
        return LLMResult(
            raw_text="mock-error",
            payload=None,
            latency_ms=8,
            provider="openai",
            model="gpt-4.1-mini",
            error=error_code,
            token_usage=None,
        )

    monkeypatch.setattr("agents.llm_client.generate_json", _mock_generate_json)
    raw = {
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "known_objections": ["budget timing"],
        "last_touch_summary": "Waiting after pricing review.",
    }

    result = context_agent(raw, _signal(urgency="medium", stalled=True))

    assert result.persona == "VP Sales"
    assert result.deal_stage == "proposal"
    assert result.known_objections == ["budget timing"]
    assert result.recent_timeline == ["Waiting after pricing review."]
    assert result.recommended_tone == "consultative"
