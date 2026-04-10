from __future__ import annotations

from api.dependencies import engine
from api.dto import ApproveActionRequest, EditActionRequest, RejectActionRequest


def approve_action(payload: ApproveActionRequest) -> dict:
    return engine.approve_action(payload.action_id)


def reject_action(payload: RejectActionRequest) -> dict:
    return engine.reject_action(payload.action_id, payload.reason)


def edit_action(payload: EditActionRequest) -> dict:
    edits = {"preview": payload.preview, "subject": payload.subject, "body": payload.body}
    edits = {k: v for k, v in edits.items() if v is not None}
    return engine.approve_action(payload.action_id, edited_fields=edits, approved_with_edits=True)
