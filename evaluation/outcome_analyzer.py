"""
Purpose:
Evaluation module `outcome_analyzer` for analyzing outcomes and generating learning signals.

Technical Details:
Calculates metrics/insights from execution traces and feeds feedback artifacts to memory for future decisions.
"""

from __future__ import annotations

from agents.contracts import ExecutionOutcome


def classify_outcome(outcome: ExecutionOutcome) -> str:
    if outcome.meeting_booked:
        return "positive"
    if outcome.reply_received:
        return "positive"
    return "neutral"
