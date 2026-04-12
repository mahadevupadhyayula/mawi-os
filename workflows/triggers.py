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



CRM_SYNC_POST_ACTION_EVENTS = {
    "post_action_execution",
    "action_executed",
}


def _crm_sync_required(raw_data: dict) -> bool:
    explicit = raw_data.get("crm_sync_required")
    if explicit is not None:
        return bool(explicit)

    crm_state = raw_data.get("crm_state")
    if isinstance(crm_state, dict):
        if crm_state.get("sync_required") is not None:
            return bool(crm_state.get("sync_required"))
        pending = crm_state.get("pending_updates")
        if isinstance(pending, list) and len(pending) > 0:
            return True

    pending_updates = raw_data.get("crm_pending_updates")
    if isinstance(pending_updates, list) and len(pending_updates) > 0:
        return True

    return False


def should_trigger_crm_sync(raw_data: dict) -> bool:
    trigger_source = str(raw_data.get("trigger_source", "")).strip().lower()
    trigger_event = str(raw_data.get("trigger_event", "")).strip().lower()

    explicit_api_trigger = trigger_source == "api" and trigger_event in {"explicit", "manual", "crm_sync"}
    post_action_event_trigger = trigger_event in CRM_SYNC_POST_ACTION_EVENTS or bool(raw_data.get("post_action_execution"))

    if explicit_api_trigger:
        return _crm_sync_required(raw_data) or bool(raw_data.get("force_crm_sync", True))

    if post_action_event_trigger:
        has_execution_reference = bool(raw_data.get("action_id") or raw_data.get("execution_id"))
        return has_execution_reference or _crm_sync_required(raw_data)

    return False
