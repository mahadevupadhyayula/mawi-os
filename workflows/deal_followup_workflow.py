from __future__ import annotations

from context.envelope import build_initial_envelope
from context.validators import validate_trigger
from context.schemas import OutcomeSignal
from orchestrator.engine import WorkflowEngine


def run_deal_followup_workflow(engine: WorkflowEngine, deal_id: str, raw_data: dict, outcome: OutcomeSignal | None = None):
    envelope = build_initial_envelope(deal_id=deal_id, raw_data=raw_data)
    if not validate_trigger(envelope, no_reply_days_threshold=5):
        envelope.meta.workflow_stage = "not_triggered"
        return envelope
    return engine.run_workflow(envelope, outcome=outcome)
