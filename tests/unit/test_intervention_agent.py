from agents.intervention_agent import intervention_agent
from context.models import InterventionDecisionContext
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


def test_intervention_agent_renders_prompt_with_expected_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_render(prompt_name: str, *, prompt_contract: dict[str, object], **_kwargs: object) -> str:
        captured["prompt_name"] = prompt_name
        captured["prompt_contract"] = dict(prompt_contract)
        return "ok"

    monkeypatch.setattr("agents.intervention_agent.render_prompt", _fake_render)
    intervention_agent(_signal(), _deal())

    assert captured["prompt_name"] == "intervention_prompt.txt"
    contract = captured["prompt_contract"]
    assert isinstance(contract, dict)
    assert contract["workflow_id"] == "deal_intervention_workflow"
    assert contract["stage_name"] == "intervention_agent"
    assert contract["policy_mode"] == "strategy_only"
    assert contract["output_model"] is InterventionDecisionContext


def test_intervention_agent_is_deterministic_for_monitor_path() -> None:
    first = intervention_agent(_signal(stalled=True, urgency="low"), _deal(objections=["pricing"]))
    second = intervention_agent(_signal(stalled=True, urgency="low"), _deal(objections=["pricing"]))

    assert first.result == "monitor"
    assert second.result == "monitor"
    assert first.reason == second.reason
    assert first.reasoning == second.reasoning
    assert first.confidence == second.confidence == 0.74
