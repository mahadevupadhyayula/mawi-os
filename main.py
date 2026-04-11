"""
Purpose:
Runs a local demo of the MAWI MVP workflow from signal intake through approval and outcome evaluation.

Technical Details:
Uses WorkflowAPI as the single integration surface, prints workflow snapshots with pprint, and exercises start/approve/state retrieval in sequence.
"""

from __future__ import annotations

from pprint import pprint

from api.service import WorkflowAPI


def run_demo() -> None:
    api = WorkflowAPI()
    deal_id = "deal-1001"

    print("=== Start workflow ===")
    state = api.start_workflow(deal_id)
    pprint({"stage": state["meta"]["workflow_stage"], "action_status": state.get("action_context", {}).get("status")})

    actions = api.get_actions()
    print("=== Pending actions ===")
    pprint(actions)

    if actions:
        action_id = actions[0]["action_id"]
        print("=== Approve action and resume ===")
        api.approve_action(action_id, approver="manager-1", reply_received=True)

    final_state = api.get_deal_state(deal_id)
    print("=== Final deal state ===")
    pprint(
        {
            "stage": final_state["meta"]["workflow_stage"],
            "execution_status": final_state.get("execution_context", {}).get("status"),
            "outcome_label": final_state.get("outcome_context", {}).get("outcome_label"),
            "insight": final_state.get("outcome_context", {}).get("insight"),
        }
    )


def run_new_deal_demo() -> None:
    api = WorkflowAPI()
    deal_id = "deal-2001"

    print("=== Start new-deal outreach workflow ===")
    state = api.start_workflow(
        deal_id,
        workflow_name="new_deal_outreach_workflow",
    )
    pprint(
        {
            "workflow": "new_deal_outreach_workflow",
            "stage": state["meta"]["workflow_stage"],
            "action_status": state.get("action_context", {}).get("status"),
        }
    )


if __name__ == "__main__":
    run_demo()
    run_new_deal_demo()
