from __future__ import annotations

from agents.crm_agent import crm_agent
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
