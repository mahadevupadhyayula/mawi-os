"""
Purpose:
Approval module `queue` for human review and action lifecycle control.

Technical Details:
Encodes approval states/policies and transitions so orchestrator resumes execution only after validated decisions.
"""

from __future__ import annotations

from typing import Dict, List


class ApprovalQueue:
    def __init__(self) -> None:
        self._actions: Dict[str, dict] = {}

    def enqueue(self, action: dict) -> None:
        self._actions[action["action_id"]] = action

    def get(self, action_id: str) -> dict | None:
        return self._actions.get(action_id)

    def list_actions(self, status: str | None = None) -> List[dict]:
        values = list(self._actions.values())
        if status:
            return [v for v in values if v.get("status") == status]
        return values
