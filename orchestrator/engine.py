from __future__ import annotations

from typing import Dict

from agents.action_agent import action_agent
from agents.context_agent import context_agent
from agents.evaluator_agent import evaluator_agent
from agents.execution_agent import execution_agent
from agents.signal_agent import signal_agent
from agents.strategist_agent import strategist_agent
from context.schemas import ActionStatus, ContextEnvelope, OutcomeSignal
from memory.long_term_store import LongTermMemory
from memory.short_term_store import ShortTermMemory
from orchestrator.retry import with_retry
from orchestrator.stage_logger import log_stage
from workflows.policies import requires_approval


class ApprovalQueue:
    def __init__(self) -> None:
        self._queue: Dict[str, dict] = {}

    def upsert(self, action: dict) -> None:
        self._queue[action["action_id"]] = action

    def get(self, action_id: str) -> dict | None:
        return self._queue.get(action_id)

    def all(self) -> list[dict]:
        return list(self._queue.values())


class WorkflowEngine:
    def __init__(self, approval_threshold: float = 0.75) -> None:
        self.approval_threshold = approval_threshold
        self.approval_queue = ApprovalQueue()
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.dead_letter: list[dict] = []

    def run_workflow(self, envelope: ContextEnvelope, outcome: OutcomeSignal | None = None) -> ContextEnvelope:
        run_id = envelope.meta.workflow_run_id
        deal_id = envelope.meta.deal_id
        try:
            for stage_name, stage_fn in [
                ("signal_agent", lambda: signal_agent(envelope)),
                ("context_agent", lambda: context_agent(envelope)),
                ("strategist_agent", lambda: strategist_agent(envelope)),
                ("action_agent", lambda: action_agent(envelope)),
            ]:
                log_stage(stage_name, deal_id, run_id)
                envelope = with_retry(stage_fn)

            action = envelope.action_context.current
            if action:
                needs_approval = requires_approval(action.confidence, self.approval_threshold)
                action.structured["status"] = ActionStatus.PENDING_APPROVAL if needs_approval else ActionStatus.APPROVED
                if needs_approval:
                    self.approval_queue.upsert(
                        {
                            "action_id": action.structured["action_id"],
                            "type": action.structured["type"],
                            "preview": action.structured["preview"],
                            "confidence": action.confidence,
                            "status": ActionStatus.PENDING_APPROVAL,
                            "deal_id": deal_id,
                        }
                    )

            log_stage("execution_agent", deal_id, run_id)
            envelope = with_retry(lambda: execution_agent(envelope))

            if outcome is None:
                outcome = OutcomeSignal(deal_id=deal_id, replied=False, notes="Outcome pending")

            log_stage("evaluator_agent", deal_id, run_id)
            envelope = with_retry(lambda: evaluator_agent(envelope, outcome))
            self.short_term.save_envelope(envelope)
            self._write_long_term(envelope)
            return envelope
        except Exception as exc:
            self.dead_letter.append({"deal_id": deal_id, "run_id": run_id, "error": str(exc)})
            raise

    def _write_long_term(self, envelope: ContextEnvelope) -> None:
        if envelope.action_context.current:
            self.long_term.record_action(envelope.action_context.current.structured)
        if envelope.outcome_context.current:
            out = envelope.outcome_context.current.structured
            self.long_term.record_outcome(out)
            persona = envelope.deal_context.current.structured.get("persona", "unknown") if envelope.deal_context.current else "unknown"
            self.long_term.record_persona_insight({"persona": persona, "insight": out.get("insight")})

    def approve_action(self, action_id: str, edited_fields: dict | None = None, approved_with_edits: bool = False) -> dict:
        action = self.approval_queue.get(action_id)
        if not action:
            raise ValueError("Action not found")
        action["status"] = ActionStatus.APPROVED_WITH_EDITS if approved_with_edits else ActionStatus.APPROVED
        if edited_fields:
            action.update(edited_fields)
        return action

    def reject_action(self, action_id: str, reason: str) -> dict:
        action = self.approval_queue.get(action_id)
        if not action:
            raise ValueError("Action not found")
        action["status"] = ActionStatus.REJECTED
        action["reason"] = reason
        return action
