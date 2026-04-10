from __future__ import annotations

from context.schemas import OutcomeSignal


def ingest_outcome(payload: dict) -> OutcomeSignal:
    return OutcomeSignal(**payload)
