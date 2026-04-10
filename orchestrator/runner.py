from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context.schemas import OutcomeSignal
from orchestrator.engine import WorkflowEngine
from tools.deal_data_tool import fetch_deal_data
from workflows.deal_followup_workflow import run_deal_followup_workflow


def example_run() -> dict:
    engine = WorkflowEngine(approval_threshold=0.75)
    fetched = fetch_deal_data("deal_001")
    raw = fetched["payload"]
    outcome = OutcomeSignal(deal_id="deal_001", replied=True, response_latency_days=2, notes="Replied after follow-up")
    envelope = run_deal_followup_workflow(engine, deal_id="deal_001", raw_data=raw, outcome=outcome)
    return {
        "workflow_stage": envelope.meta.workflow_stage,
        "action_context": envelope.action_context.current.structured if envelope.action_context.current else None,
        "execution_context": envelope.execution_context.current.structured if envelope.execution_context.current else None,
        "outcome_context": envelope.outcome_context.current.structured if envelope.outcome_context.current else None,
        "actions_queue": engine.approval_queue.all(),
        "dead_letter": engine.dead_letter,
    }


if __name__ == "__main__":
    print(json.dumps(example_run(), indent=2, default=str))
