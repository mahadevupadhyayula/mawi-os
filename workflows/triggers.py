"""
Purpose:
Workflow module `triggers` that defines triggers, registration, or stage flow behavior.

Technical Details:
Declares composable workflow contracts used by orchestration to run repeatable business processes with typed context.
"""

from __future__ import annotations


def should_trigger_deal_followup(raw_data: dict) -> bool:
    return int(raw_data.get("days_since_reply", 0)) >= 5
