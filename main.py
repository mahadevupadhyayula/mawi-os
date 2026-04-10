from __future__ import annotations

import json

from context.schemas import OutcomeSignal
from orchestrator.engine import WorkflowEngine
from tools.deal_data_tool import fetch_deal_data
from workflows.deal_followup_workflow import run_deal_followup_workflow


def run_example() -> None:
    engine = WorkflowEngine(approval_threshold=0.8)
    raw = fetch_deal_data("deal_123")["payload"]
    outcome = OutcomeSignal(deal_id="deal_123", replied=True, meeting_booked=False, response_latency_days=1)
    envelope = run_deal_followup_workflow(engine, deal_id="deal_123", raw_data=raw, outcome=outcome)

    print("=== SAMPLE INPUT ===")
    print(json.dumps(raw, indent=2))
    print("=== SAMPLE OUTPUT CONTEXT ===")
    print(json.dumps(envelope.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    run_example()
