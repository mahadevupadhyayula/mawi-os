from __future__ import annotations

from agents.contracts import ExecutionOutcome


def classify_outcome(outcome: ExecutionOutcome) -> str:
    if outcome.meeting_booked:
        return "positive"
    if outcome.reply_received:
        return "positive"
    return "neutral"
