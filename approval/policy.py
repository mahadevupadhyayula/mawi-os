"""
Purpose:
Approval module `policy` for human review and action lifecycle control.

Technical Details:
Encodes approval states/policies and transitions so orchestrator resumes execution only after validated decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from context.models import ActionStep
from workflows.registry import get_workflow


def requires_approval(confidence: float, threshold: float) -> bool:
    return confidence < threshold


@dataclass(frozen=True)
class ChannelPolicyDecision:
    allowed: bool
    reason: str = ""
    channel: str = ""
    risk_tier: str = "low"


_RISK_LEVELS: dict[str, int] = {"low": 1, "medium": 2, "high": 3}
_CHANNEL_RISK_TIER: dict[str, str] = {"email": "low", "crm": "low", "sms": "medium"}
_UNCERTAINTY_PHRASES: tuple[str, ...] = ("might", "maybe", "probably", "could", "possibly")
_PROHIBITED_CLAIMS: tuple[str, ...] = ("guarantee", "guaranteed", "100%", "always", "never fail")


@dataclass(frozen=True)
class OutputPolicyValidation:
    allowed: bool
    reasons: tuple[str, ...] = ()
    requires_escalation: bool = False


def risk_tier_for_channel(channel: str) -> str:
    return _CHANNEL_RISK_TIER.get(channel, "high")


def max_risk_tier_for_workflow_phase(workflow_id: str, phase: str) -> str:
    workflow = get_workflow(workflow_id)
    phase_map = workflow.config.get("max_risk_tier_by_phase", {})
    return str(phase_map.get(phase, phase_map.get("default", "high")))


def validate_step_channel_policy(
    step: ActionStep,
    *,
    allowed_channels: Iterable[str],
    max_risk_tier: str,
) -> ChannelPolicyDecision:
    normalized_channels = {channel.lower() for channel in allowed_channels}
    channel = step.channel.lower()
    risk_tier = risk_tier_for_channel(channel)

    if channel not in normalized_channels:
        return ChannelPolicyDecision(
            allowed=False,
            reason="channel_not_allowed",
            channel=channel,
            risk_tier=risk_tier,
        )

    max_risk_score = _RISK_LEVELS.get(max_risk_tier.lower(), _RISK_LEVELS["high"])
    channel_risk_score = _RISK_LEVELS.get(risk_tier, _RISK_LEVELS["high"])
    if channel_risk_score > max_risk_score:
        return ChannelPolicyDecision(
            allowed=False,
            reason="channel_risk_tier_blocked",
            channel=channel,
            risk_tier=risk_tier,
        )

    return ChannelPolicyDecision(allowed=True, channel=channel, risk_tier=risk_tier)


def validate_generated_output(step: ActionStep, *, autonomous_phase: bool, risk_tier: str) -> OutputPolicyValidation:
    body = step.body_draft.lower()
    subject = step.subject.lower()
    content = f"{subject} {body}".strip()
    reasons: list[str] = []

    if any(token in content for token in _PROHIBITED_CLAIMS):
        reasons.append("prohibited_claim_detected")
    if "legal advice" in content or "regulatory compliant" in content:
        reasons.append("legal_compliance_boundary_violation")
    if autonomous_phase and risk_tier in {"medium", "high"} and any(token in content for token in _UNCERTAINTY_PHRASES):
        reasons.append("uncertain_language_requires_review")

    if step.channel == "sms" and risk_tier in {"medium", "high"} and len(step.body_draft) > 240:
        reasons.append("high_risk_sms_too_long")

    return OutputPolicyValidation(
        allowed=not reasons,
        reasons=tuple(reasons),
        requires_escalation=bool(reasons) and (autonomous_phase or risk_tier == "high"),
    )


def escalation_instructions(validation: OutputPolicyValidation) -> str:
    if not validation.requires_escalation:
        return ""
    return (
        "Escalate to human reviewer with policy rationale, redact unsupported claims, "
        "and request explicit approval before execution."
    )
