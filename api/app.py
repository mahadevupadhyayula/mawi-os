from __future__ import annotations

from api.dto import ApproveActionRequest, EditActionRequest, RejectActionRequest
from api.routes_actions import get_actions
from api.routes_approval import approve_action, edit_action, reject_action
from api.routes_deals import get_deal_state


ROUTES = {
    "GET /api/actions": get_actions,
    "POST /api/approve_action": approve_action,
    "POST /api/reject_action": reject_action,
    "POST /api/edit_action": edit_action,
    "GET /api/deal_state": get_deal_state,
}


def example_api_usage(action_id: str, run_id: str) -> dict:
    return {
        "actions": get_actions(),
        "approve": approve_action(ApproveActionRequest(action_id=action_id)),
        "edit": edit_action(EditActionRequest(action_id=action_id, preview="Edited preview")),
        "reject": reject_action(RejectActionRequest(action_id=action_id, reason="Not aligned")),
        "deal_state": get_deal_state(run_id),
    }
