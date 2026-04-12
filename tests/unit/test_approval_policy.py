from __future__ import annotations

from approval.policy import (
    escalation_instructions,
    requires_approval,
    validate_generated_output,
    validate_step_channel_policy,
)
from context.models import ActionStep


def test_requires_approval_uses_strict_threshold_boundary() -> None:
    assert requires_approval(0.79, 0.80) is True
    assert requires_approval(0.80, 0.80) is False
    assert requires_approval(0.95, 0.80) is False


def test_validate_step_channel_policy_blocks_disallowed_channel() -> None:
    step = ActionStep(step_id="s-1", order=1, channel="sms", action_type="send_sms", body_draft="hi")

    decision = validate_step_channel_policy(step, allowed_channels=("email", "crm"), max_risk_tier="high")

    assert decision.allowed is False
    assert decision.reason == "channel_not_allowed"
    assert decision.channel == "sms"
    assert decision.risk_tier == "medium"


def test_validate_step_channel_policy_blocks_when_risk_exceeds_phase_limit() -> None:
    step = ActionStep(step_id="s-2", order=1, channel="sms", action_type="send_sms", body_draft="hi")

    decision = validate_step_channel_policy(step, allowed_channels=("sms",), max_risk_tier="low")

    assert decision.allowed is False
    assert decision.reason == "channel_risk_tier_blocked"


def test_validate_generated_output_flags_policy_violations_and_escalation() -> None:
    step = ActionStep(
        step_id="s-3",
        order=1,
        channel="sms",
        action_type="send_sms",
        subject="Guaranteed response",
        body_draft="We guarantee this will probably convert. " + ("x" * 260),
    )

    validation = validate_generated_output(step, autonomous_phase=True, risk_tier="high")

    assert validation.allowed is False
    assert "prohibited_claim_detected" in validation.reasons
    assert "uncertain_language_requires_review" in validation.reasons
    assert "high_risk_sms_too_long" in validation.reasons
    assert validation.requires_escalation is True
    assert "Escalate to human reviewer" in escalation_instructions(validation)


def test_validate_generated_output_allows_safe_content_without_escalation() -> None:
    step = ActionStep(
        step_id="s-4",
        order=1,
        channel="email",
        action_type="send_email",
        subject="Checking in",
        body_draft="Wanted to follow up on next steps.",
    )

    validation = validate_generated_output(step, autonomous_phase=False, risk_tier="low")

    assert validation.allowed is True
    assert validation.reasons == ()
    assert validation.requires_escalation is False
    assert escalation_instructions(validation) == ""
