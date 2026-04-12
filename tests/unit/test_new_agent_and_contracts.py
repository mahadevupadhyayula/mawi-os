from __future__ import annotations

from agents.contracts import AgentResult, bounded_confidence, make_result
from agents.crm_agent import crm_agent
from agents.intervention_agent import intervention_agent
from context.models import DealContext, SignalContext


def _deal_context(*, objections: list[str] | None = None) -> DealContext:
    return DealContext(
        persona="RevOps",
        deal_stage="proposal",
        known_objections=objections or [],
        recent_timeline=["demo complete"],
        recommended_tone="consultative",
        reasoning="seed",
        confidence=0.8,
    )


def test_make_result_clamps_confidence_and_preserves_warnings() -> None:
    capped_high = make_result({"k": "v"}, "high", 4.2, warnings=["warn"])
    capped_low = make_result("payload", "low", -2.0)

    assert isinstance(capped_high, AgentResult)
    assert capped_high.confidence == 1.0
    assert capped_high.warnings == ["warn"]
    assert capped_low.confidence == 0.0


def test_bounded_confidence_returns_value_within_unit_interval() -> None:
    assert bounded_confidence(0.33) == 0.33
    assert bounded_confidence(-10) == 0.0
    assert bounded_confidence(10) == 1.0


def test_crm_agent_contract_normalizes_fallback_fields_and_sync_requirement() -> None:
    raw_data = {
        "crm_record_id": "crm-fallback-1",
        "crm_pending_updates": ["owner", "next_step", 42],
        "crm_sync_required": False,
        "trigger_event": "post_action_execution",
    }

    plan = crm_agent(raw_data, _deal_context())

    assert plan.status == "approved"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.channel == "crm"
    assert step.action_type == "update_crm"
    assert "record_id=crm-fallback-1" in step.body_draft
    assert "owner; next_step; 42" in step.body_draft
    assert plan.confidence == 0.86


def test_intervention_agent_returns_monitor_for_stalled_low_risk_deals() -> None:
    signal = SignalContext(
        stalled=True,
        days_since_reply=9,
        urgency="low",
        trigger_reason="no_reply_5_days",
        reasoning="seed",
        confidence=0.8,
    )

    result = intervention_agent(signal, _deal_context(objections=["pricing"]))

    assert result.result == "monitor"
    assert "monitor" in result.reason.lower()
    assert 0.0 <= result.confidence <= 1.0
