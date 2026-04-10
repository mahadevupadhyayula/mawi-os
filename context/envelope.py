from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from context.schemas import ContextEnvelope, MetaContext


def build_initial_envelope(deal_id: str, raw_data: dict) -> ContextEnvelope:
    return ContextEnvelope(
        meta=MetaContext(
            deal_id=deal_id,
            timestamp=datetime.now(timezone.utc),
            workflow_stage="triggered",
            workflow_run_id=str(uuid4()),
        ),
        raw_data=raw_data,
    )
