"""
Purpose:
Workflow module `triggers` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations


def should_trigger_deal_followup(raw_data: dict) -> bool:
    return int(raw_data.get("days_since_reply", 0)) >= 5

NEW_DEAL_OUTBOUND_MARKERS = (
    "has_prior_outbound",
    "outbound_count",
    "last_outbound_at",
    "last_outbound_summary",
    "last_outbound_message_id",
    "prior_outreach_sent",
)


def should_trigger_new_deal_outreach(raw_data: dict) -> bool:
    days_since_reply = int(raw_data.get("days_since_reply", -1))
    if days_since_reply != 0:
        return False

    for marker in NEW_DEAL_OUTBOUND_MARKERS:
        value = raw_data.get(marker)
        if marker == "outbound_count":
            if int(value or 0) > 0:
                return False
            continue
        if value not in (None, False, "", []):
            return False

    return True

RISK_SCORE_TIERS = {
    "low": 0,
    "medium": 40,
    "high": 70,
    "critical": 90,
}


def _risk_tier_from_score(risk_score: int) -> str:
    if risk_score >= RISK_SCORE_TIERS["critical"]:
        return "critical"
    if risk_score >= RISK_SCORE_TIERS["high"]:
        return "high"
    if risk_score >= RISK_SCORE_TIERS["medium"]:
        return "medium"
    return "low"


def should_trigger_deal_intervention(raw_data: dict) -> bool:
    if bool(raw_data.get("deal_stalled")):
        return True
    if bool(raw_data.get("no_reply")):
        return True

    explicit_tier = str(raw_data.get("risk_tier", "")).strip().lower()
    if explicit_tier in {"high", "critical"}:
        return True

    risk_score = int(raw_data.get("risk_score", 0) or 0)
    inferred_tier = _risk_tier_from_score(risk_score)
    return inferred_tier in {"high", "critical"}

