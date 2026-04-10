from __future__ import annotations

import json

from api.app import ROUTES
from api.dto import ApproveActionRequest, EditActionRequest, RejectActionRequest
from api.routes_actions import get_actions
from api.routes_approval import approve_action, edit_action, reject_action
from context.schemas import OutcomeSignal
from orchestrator.engine import WorkflowEngine
from tools.deal_data_tool import fetch_deal_data
from workflows.deal_followup_workflow import run_deal_followup_workflow


def run() -> None:
    engine = WorkflowEngine(approval_threshold=0.8)
    raw = fetch_deal_data("deal_api_1")["payload"]
    _ = run_deal_followup_workflow(engine, "deal_api_1", raw, OutcomeSignal(deal_id="deal_api_1", replied=False))

    # Inject this run's queue item into API singleton for demonstration
    from api.dependencies import engine as api_engine

    api_engine.approval_queue = engine.approval_queue
    action = get_actions()["items"][0]
    action_id = action["action_id"]

    results = {
        "routes": list(ROUTES.keys()),
        "actions": get_actions(),
        "approve": approve_action(ApproveActionRequest(action_id=action_id)),
        "edit": edit_action(EditActionRequest(action_id=action_id, preview="Updated preview for approval")),
        "reject": reject_action(RejectActionRequest(action_id=action_id, reason="Testing rejection endpoint")),
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()
