"""
Purpose:
Orchestrator module `runner` for coordinating workflow execution mechanics.

Technical Details:
Handles sequencing, retries, and auditability while delegating domain decisions to dedicated agents and tools.
"""

from __future__ import annotations

from dataclasses import asdict

from agents.action_agent import action_agent
from agents.context_agent import context_agent
from agents.evaluator_agent import evaluator_agent
from agents.execution_agent import execution_agent
from agents.signal_agent import signal_agent
from agents.strategist_agent import strategist_agent
from agents.contracts import ExecutionOutcome
from approval.policy import requires_approval
from approval.queue import ApprovalQueue
from context.envelope import append_or_refine_section, set_stage
from context.models import ContextEnvelope, MetaContext
from data.models import RUN_STATUS_COMPLETED, RUN_STATUS_RUNNING, RUN_STATUS_SKIPPED, RUN_STATUS_WAITING_APPROVAL, WORKFLOW_NAME
from data.repositories import ActionRepository, OutcomeRepository, WorkflowRepository
from memory.long_term_store import LongTermMemory
from memory.memory_models import OutcomeRecord
from memory.short_term_store import ShortTermMemory
from tools.deal_tool import fetch_deal_data
from workflows.triggers import should_trigger_deal_followup
from orchestrator.audit_logger import log_step
from orchestrator.retry_policy import with_retries


class WorkflowOrchestrator:
    def __init__(self, *, approval_threshold: float = 0.8) -> None:
        self.approval_threshold = approval_threshold
        self.queue = ApprovalQueue()
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.workflow_repo = WorkflowRepository()
        self.action_repo = ActionRepository()
        self.outcome_repo = OutcomeRepository()
        self._run_ids: dict[str, str] = {}

    def _snapshot(self, deal_id: str, envelope: ContextEnvelope, source_agent: str | None = None) -> None:
        run_id = self._run_ids.get(deal_id)
        if run_id:
            self.workflow_repo.append_envelope_snapshot(run_id, envelope, source_agent=source_agent)

    def run_workflow(self, deal_id: str) -> ContextEnvelope:
        raw = fetch_deal_data(deal_id)
        envelope = ContextEnvelope(meta=MetaContext(deal_id=deal_id), raw_data=raw)
        self.workflow_repo.create_or_update_deal(deal_id, raw)
        run_id = self.workflow_repo.create_run(deal_id, WORKFLOW_NAME, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._run_ids[deal_id] = run_id
        self._snapshot(deal_id, envelope, source_agent="system")

        if not should_trigger_deal_followup(raw):
            set_stage(envelope, "initialized")
            log_step("trigger", "Deal did not meet stalled threshold; workflow skipped.")
            self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_SKIPPED, complete=True)
            self._snapshot(deal_id, envelope, source_agent="trigger")
            return envelope

        signal = with_retries(lambda: signal_agent(raw))
        append_or_refine_section(envelope, agent_name="signal_agent", section_value=signal)
        set_stage(envelope, "signal_done")
        self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="signal_agent")
        log_step("signal_agent", "Signal context generated.")

        deal = with_retries(lambda: context_agent(raw, envelope.signal_context))
        append_or_refine_section(envelope, agent_name="context_agent", section_value=deal)
        set_stage(envelope, "context_done")
        self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="context_agent")
        log_step("context_agent", "Deal context generated.")

        decision = with_retries(lambda: strategist_agent(envelope.signal_context, envelope.deal_context))
        append_or_refine_section(envelope, agent_name="strategist_agent", section_value=decision)
        set_stage(envelope, "strategy_done")
        self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="strategist_agent")
        log_step("strategist_agent", "Decision context generated.")

        action = with_retries(lambda: action_agent(envelope.decision_context, envelope.deal_context))
        if requires_approval(action.confidence, self.approval_threshold):
            action.status = "pending_approval"
            self.queue.enqueue(asdict(action))
            set_stage(envelope, "waiting_approval")
            self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_WAITING_APPROVAL)
            log_step("action_agent", "Action routed to approval queue.")
        else:
            action.status = "approved"
            set_stage(envelope, "action_done")
            self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
            log_step("action_agent", "Action auto-approved by policy.")

        append_or_refine_section(envelope, agent_name="action_agent", section_value=action)
        self.action_repo.upsert_action(run_id, deal_id, action)
        self._snapshot(deal_id, envelope, source_agent="action_agent")
        self.long_memory.add_outcome(OutcomeRecord(deal_id=deal_id, action_id=action.action_id, outcome_label="pending", insight="Action created"))
        self.short_memory.save(deal_id, envelope)
        return envelope

    def resume_after_approval(self, envelope: ContextEnvelope, outcome: ExecutionOutcome) -> ContextEnvelope:
        action_ctx = envelope.action_context
        if action_ctx is None:
            raise ValueError("Missing action_context")
        action_ctx.status = "approved"

        run_id = self._run_ids.get(envelope.meta.deal_id)
        execution = with_retries(
            lambda: execution_agent(action_ctx, deal_id=envelope.meta.deal_id, contact_name=envelope.raw_data.get("contact_name", "Prospect"))
        )
        append_or_refine_section(envelope, agent_name="execution_agent", section_value=execution)
        set_stage(envelope, "execution_done")
        if run_id:
            self.outcome_repo.record_execution(run_id, envelope.meta.deal_id, action_ctx.action_id, execution)
            self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
            self._snapshot(envelope.meta.deal_id, envelope, source_agent="execution_agent")
        log_step("execution_agent", f"Execution status={execution.status}")

        outcome_ctx = with_retries(lambda: evaluator_agent(execution, outcome))
        append_or_refine_section(envelope, agent_name="evaluator_agent", section_value=outcome_ctx)
        set_stage(envelope, "evaluation_done")
        if run_id:
            self.outcome_repo.record_outcome(run_id, envelope.meta.deal_id, action_ctx.action_id, outcome_ctx)
            persona = envelope.deal_context.persona if envelope.deal_context else "unknown"
            self.outcome_repo.add_persona_insight(persona, outcome_ctx.insight, outcome_ctx.confidence)
            self.workflow_repo.update_run(run_id, envelope.meta.workflow_stage, RUN_STATUS_COMPLETED, complete=True)
            self._snapshot(envelope.meta.deal_id, envelope, source_agent="evaluator_agent")
        log_step("evaluator_agent", f"Outcome label={outcome_ctx.outcome_label}")

        self.long_memory.add_outcome(
            OutcomeRecord(
                deal_id=envelope.meta.deal_id,
                action_id=action_ctx.action_id,
                outcome_label=outcome_ctx.outcome_label,
                insight=outcome_ctx.insight,
            )
        )
        self.short_memory.save(envelope.meta.deal_id, envelope)
        return envelope
