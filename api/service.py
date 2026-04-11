"""
Purpose:
API module `service` that exposes workflow operations to callers.

Technical Details:
Provides service-facing interfaces for human-in-the-loop actions while keeping transport concerns decoupled from domain logic.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from agents.contracts import ExecutionOutcome
from approval.action_lifecycle import approve, edit, reject
from orchestrator.runner import WorkflowOrchestrator


class WorkflowAPI:
    """Service methods that map directly to required endpoints:
    - GET /actions -> get_actions
    - POST /approve_action -> approve_action
    - POST /reject_action -> reject_action
    - POST /edit_action -> edit_action
    - GET /deal_state -> get_deal_state
    """

    def __init__(self, orchestrator: WorkflowOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or WorkflowOrchestrator()
        self._deal_envelopes: Dict[str, Any] = {}

    def start_workflow(self, deal_id: str) -> dict:
        envelope = self.orchestrator.run_workflow(deal_id)
        self._deal_envelopes[deal_id] = envelope
        return asdict(envelope)

    def get_actions(self) -> List[dict]:
        return self.orchestrator.queue.list_actions()

    def approve_action(self, action_id: str, approver: str, *, reply_received: bool = True, meeting_booked: bool = False) -> dict:
        action = self.orchestrator.queue.get(action_id)
        if not action:
            raise ValueError("Action not found")
        updated = approve(action, approver)
        self.orchestrator.queue.enqueue(updated)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._deal_envelopes[deal_id]
        envelope.action_context.status = "approved"
        outcome = ExecutionOutcome(reply_received=reply_received, meeting_booked=meeting_booked)
        resumed = self.orchestrator.resume_after_approval(envelope, outcome)
        self._deal_envelopes[deal_id] = resumed
        return {"status": "approved", "deal_id": deal_id, "action_id": action_id}

    def reject_action(self, action_id: str, approver: str, reason: str) -> dict:
        action = self.orchestrator.queue.get(action_id)
        if not action:
            raise ValueError("Action not found")
        updated = reject(action, approver, reason)
        self.orchestrator.queue.enqueue(updated)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._deal_envelopes[deal_id]
        envelope.action_context.status = "rejected"
        return {"status": "rejected", "deal_id": deal_id, "action_id": action_id, "reason": reason}

    def edit_action(self, action_id: str, approver: str, *, preview: str | None = None, body_draft: str | None = None) -> dict:
        action = self.orchestrator.queue.get(action_id)
        if not action:
            raise ValueError("Action not found")
        updated = edit(action, approver, preview=preview, body_draft=body_draft)
        self.orchestrator.queue.enqueue(updated)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._deal_envelopes[deal_id]
        if preview is not None:
            envelope.action_context.preview = preview
        if body_draft is not None:
            envelope.action_context.body_draft = body_draft
        envelope.action_context.status = "pending_approval"
        return {"status": "edited", "deal_id": deal_id, "action_id": action_id}

    def get_deal_state(self, deal_id: str) -> dict:
        envelope = self._deal_envelopes.get(deal_id)
        if envelope is None:
            raise ValueError("Deal state not found")
        return asdict(envelope)

    def _find_deal_for_action(self, action_id: str) -> str:
        for deal_id, envelope in self._deal_envelopes.items():
            if envelope.action_context and envelope.action_context.action_id == action_id:
                return deal_id
        raise ValueError("Deal for action not found")
