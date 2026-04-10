from __future__ import annotations


def deal_followup_trigger(no_reply_days: int, threshold_days: int = 5) -> bool:
    return no_reply_days >= threshold_days
