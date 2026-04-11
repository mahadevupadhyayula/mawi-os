from __future__ import annotations


def should_trigger_deal_followup(raw_data: dict) -> bool:
    return int(raw_data.get("days_since_reply", 0)) >= 5
