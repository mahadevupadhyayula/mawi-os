from __future__ import annotations

from api.dependencies import engine


def get_deal_state(run_id: str) -> dict:
    envelope = engine.short_term.get_envelope(run_id)
    if not envelope:
        raise ValueError("deal state not found")
    return envelope.to_dict()
