from __future__ import annotations

from context.schemas import ContextEnvelope


def validate_trigger(envelope: ContextEnvelope, no_reply_days_threshold: int = 5) -> bool:
    raw = envelope.raw_data
    no_reply_days = int(raw.get("no_reply_days", 0))
    return no_reply_days >= no_reply_days_threshold
