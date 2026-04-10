from __future__ import annotations

from context.schemas import OutcomeSignal


def compare_action_outcome(outcome: OutcomeSignal) -> dict:
    return {
        "success": bool(outcome.replied or outcome.meeting_booked),
        "response_latency_days": outcome.response_latency_days,
    }
