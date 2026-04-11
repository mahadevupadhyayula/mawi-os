"""
Purpose:
Approval module `action_lifecycle` for human review and action lifecycle control.

Technical Details:
Encodes approval states/policies and transitions so orchestrator resumes execution only after validated decisions.
"""

from __future__ import annotations


def approve(action: dict, approver: str) -> dict:
    action = dict(action)
    action["status"] = "approved"
    action["approved_by"] = approver
    return action


def reject(action: dict, approver: str, reason: str) -> dict:
    action = dict(action)
    action["status"] = "rejected"
    action["rejected_by"] = approver
    action["rejection_reason"] = reason
    return action


def edit(action: dict, approver: str, preview: str | None = None, body_draft: str | None = None) -> dict:
    action = dict(action)
    if preview is not None:
        action["preview"] = preview
    if body_draft is not None:
        action["body_draft"] = body_draft
    action["edited_by"] = approver
    action["status"] = "pending_approval"
    return action
