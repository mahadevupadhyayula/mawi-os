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


def risk_tier_for_channel(channel: str) -> str:
    return _CHANNEL_RISK_TIER.get(channel, "high")


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
