"""
Purpose:
Evaluation module `outcome_analyzer` for analyzing outcomes and generating learning signals.

Technical Details:
Calculates metrics/insights from execution traces and feeds feedback artifacts to memory for future decisions.
"""

from __future__ import annotations

from agents.contracts import ExecutionOutcome


def classify_outcome(outcome: ExecutionOutcome) -> str:
    return classify_outcome_detailed(outcome, execution_success=True)


def classify_outcome_detailed(outcome: ExecutionOutcome, *, execution_success: bool) -> str:
    if not execution_success:
        return "delivery_failure"
    if outcome.meeting_booked:
        return "positive"
    if outcome.reply_received:
        return "positive"
    if isinstance(outcome.notes, str) and "interested" in outcome.notes.lower():
        return "delayed_positive"
    return "neutral"
