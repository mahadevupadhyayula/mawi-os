"""
Purpose:
Orchestrator module `runner` for coordinating workflow execution mechanics.

Technical Details:
Handles sequencing, retries, and auditability while delegating domain decisions to dedicated agents and tools.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Callable, TypeVar

from agents.action_agent import action_agent
from agents.crm_agent import crm_agent
from agents.context_agent import context_agent
from agents.evaluator_agent import evaluator_agent
from agents.execution_agent import execution_agent
from agents.intervention_agent import intervention_agent
from agents.signal_agent import signal_agent
from agents.strategist_agent import strategist_agent
from agents.prompt_templates import attach_prompt_outcome, attach_prompt_outcome_metrics
from agents.contracts import ExecutionOutcome
from approval.policy import requires_approval
from approval.queue import ApprovalQueue
from context.envelope import append_or_refine_section, set_stage
from context.models import ActionContext, ActionPlanContext, ActionStep, ContextEnvelope, MetaContext
from data.models import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_RUNNING, RUN_STATUS_SKIPPED, RUN_STATUS_WAITING_APPROVAL
from data.repositories import ActionRepository, OutcomeRepository, WorkflowRepository
from evaluation.metrics import WorkflowPathMetrics
from memory.long_term_store import LongTermMemory
from memory.memory_models import OutcomeRecord
from memory.retrieval import retrieve_persona_evidence
from memory.short_term_store import ShortTermMemory
from orchestrator.audit_logger import log_step
from orchestrator.retry_policy import with_retries
from tools.deal_tool import fetch_deal_data
from workflows.registry import get_workflow

T = TypeVar("T")


def _memory_influence_summary(envelope: ContextEnvelope) -> str:
    decision = envelope.decision_context
    if decision is None:
        return "memory_used=0;memory_impact=0.000;memory_strategy=none;memory_rationale=unavailable"
    used_count = len(decision.memory_evidence_used or [])
    rationale = (decision.memory_rationale or "none").replace(";", ",")
    return (
        f"memory_used={used_count};"
        f"memory_impact={decision.memory_confidence_impact:.3f};"
        f"memory_strategy={decision.strategy_type or 'unknown'};"
        f"memory_rationale={rationale}"
    )


class WorkflowOrchestrator:
    def __init__(self, *, approval_threshold: float = 0.8) -> None:
        self.approval_threshold = approval_threshold
        self.queue = ApprovalQueue()
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.workflow_repo = WorkflowRepository()
        self.action_repo = ActionRepository()
        self.outcome_repo = OutcomeRepository()
        self.path_metrics = WorkflowPathMetrics()
        self._run_ids: dict[str, str] = {}

    def _update_run_status(
        self,
        run_id: str,
        stage: str,
        status: str,
        *,
        last_error: str | None = None,
        complete: bool = False,
    ) -> None:
        self.workflow_repo.update_run(run_id, stage, status, last_error=last_error, complete=complete)
        self.path_metrics.increment(status)

    def _serialize_error(self, workflow_id: str, step: str, retry_count: int, error: Exception) -> str:
        return json.dumps(
            {
                "workflow_id": workflow_id,
                "step": step,
                "retry_count": retry_count,
                "error_class": error.__class__.__name__,
                "message": str(error),
                "terminal": bool(getattr(error, "terminal_retry_error", False)),
            },
            sort_keys=True,
        )

    def _execute_with_step_audit(
        self,
        *,
        workflow_id: str,
        step: str,
        fn: Callable[[], T],
        retries: int = 2,
        backoff_seconds: float | None = 0.1,
        terminal_error_classes: tuple[type[Exception], ...] | None = (ValueError, TypeError),
    ) -> T:
        retry_count = 0
        started = time.perf_counter()
        def _capture_retry(attempt: int, _exc: Exception, _delay: float) -> None:
            nonlocal retry_count
            retry_count = attempt

        try:
            result = with_retries(
                fn,
                retries=retries,
                backoff_seconds=backoff_seconds,
                terminal_error_classes=terminal_error_classes,
                on_retry=_capture_retry,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_step(
                step,
                "Step execution failed.",
                workflow_id=workflow_id,
                step_name=step,
                duration_ms=duration_ms,
                retry_count=retry_count,
                error_class=exc.__class__.__name__,
            )
            raise
        finally:
            if "result" in locals():
                duration_ms = int((time.perf_counter() - started) * 1000)
                log_step(
                    step,
                    "Step execution completed.",
                    workflow_id=workflow_id,
                    step_name=step,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                    error_class=None,
                )

    def _snapshot(self, deal_id: str, envelope: ContextEnvelope, source_agent: str | None = None) -> None:
        run_id = self._run_ids.get(deal_id)
        if run_id:
            self.workflow_repo.append_envelope_snapshot(run_id, envelope, source_agent=source_agent)

    def _outcome_from_raw_data(self, raw_data: dict) -> ExecutionOutcome:
        return ExecutionOutcome(
            reply_received=bool(raw_data.get("reply_received", False)),
            meeting_booked=bool(raw_data.get("meeting_booked", False)),
            notes=str(raw_data.get("execution_notes", "")),
        )

    def run_workflow(
        self,
        deal_id: str,
        workflow_name: str | None = None,
        *,
        trigger_context: dict | None = None,
    ) -> ContextEnvelope:
        raw = fetch_deal_data(deal_id)
        if trigger_context:
            raw.update(trigger_context)
        envelope = ContextEnvelope(meta=MetaContext(deal_id=deal_id), raw_data=raw)
        self.workflow_repo.create_or_update_deal(deal_id, raw)
        workflow = get_workflow(workflow_name)
        run_id = self.workflow_repo.create_run(deal_id, workflow.workflow_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._run_ids[deal_id] = run_id
        self._snapshot(deal_id, envelope, source_agent="system")

        if not workflow.trigger(raw):
            set_stage(envelope, "initialized")
            log_step("trigger", f"Deal did not meet trigger criteria for {workflow.workflow_id}; workflow skipped.")
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_SKIPPED, complete=True)
            self._snapshot(deal_id, envelope, source_agent="trigger")
            return envelope

        try:
            for step in workflow.steps:
                should_continue = self._execute_workflow_step(workflow.workflow_id, step, deal_id, run_id, envelope)
                if not should_continue:
                    break
        except Exception as exc:  # noqa: BLE001
            payload = self._serialize_error(workflow.workflow_id, envelope.meta.workflow_stage, 0, exc)
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_FAILED, last_error=payload, complete=True)
            self._snapshot(deal_id, envelope, source_agent="system")
            raise

        self.short_memory.save(deal_id, envelope)
        return envelope

    def _execute_workflow_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        stage_handlers: dict[str, Callable[[], bool]] = {
            "signal_agent": lambda: self._handle_signal_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "context_agent": lambda: self._handle_context_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "strategist_agent": lambda: self._handle_strategist_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "intervention_agent": lambda: self._handle_intervention_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "action_agent": lambda: self._handle_action_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "crm_agent": lambda: self._handle_crm_agent_step(workflow_id, step, deal_id, run_id, envelope),
            "execution_agent": lambda: True,
            "evaluator_agent": lambda: True,
        }
        handler = stage_handlers.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        return handler()

    def _handle_signal_agent_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        signal = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: signal_agent(envelope.raw_data, workflow_id=workflow_id, run_id=run_id),
        )
        append_or_refine_section(envelope, agent_name="signal_agent", section_value=signal)
        set_stage(envelope, "signal_done")
        self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="signal_agent")
        return True

    def _handle_context_agent_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        deal = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: context_agent(
                envelope.raw_data,
                envelope.signal_context,
                workflow_id=workflow_id,
                run_id=run_id,
            ),
        )
        append_or_refine_section(envelope, agent_name="context_agent", section_value=deal)
        set_stage(envelope, "context_done")
        self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="context_agent")
        return True

    def _handle_strategist_agent_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        persona = envelope.deal_context.persona if envelope.deal_context else "unknown"
        memory_evidence = retrieve_persona_evidence(
            memory=self.long_memory,
            outcome_repo=self.outcome_repo,
            persona=persona,
        )
        envelope.raw_data["memory_inputs_strategist"] = memory_evidence
        decision = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: strategist_agent(
                envelope.signal_context,
                envelope.deal_context,
                memory_evidence,
                workflow_id=workflow_id,
                run_id=run_id,
            ),
        )
        append_or_refine_section(envelope, agent_name="strategist_agent", section_value=decision)
        set_stage(envelope, "strategy_done")
        self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="strategist_agent")
        return True

    def _handle_intervention_agent_step(
        self,
        workflow_id: str,
        step: str,
        deal_id: str,
        run_id: str,
        envelope: ContextEnvelope,
    ) -> bool:
        intervention = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: intervention_agent(
                envelope.signal_context,
                envelope.deal_context,
                workflow_id=workflow_id,
                run_id=run_id,
            ),
        )
        append_or_refine_section(envelope, agent_name="intervention_agent", section_value=intervention)
        set_stage(envelope, "intervention_done")
        self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self._snapshot(deal_id, envelope, source_agent="intervention_agent")
        return True

    def _handle_action_agent_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        persona = envelope.deal_context.persona if envelope.deal_context else "unknown"
        memory_evidence = retrieve_persona_evidence(
            memory=self.long_memory,
            outcome_repo=self.outcome_repo,
            persona=persona,
        )
        envelope.raw_data["memory_inputs_action"] = memory_evidence
        action_plan = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: action_agent(
                envelope.decision_context,
                envelope.deal_context,
                workflow_id=workflow_id,
                run_id=run_id,
            ),
        )
        if not action_plan.steps:
            raise ValueError("action_agent returned an empty action plan")
        first_step = sorted(action_plan.steps, key=lambda item: item.order)[0]
        action = ActionContext(
            action_id=first_step.step_id,
            type=first_step.action_type,
            subject=first_step.subject,
            preview=first_step.preview,
            body_draft=first_step.body_draft,
            status=first_step.status,
            reasoning=action_plan.reasoning,
            confidence=action_plan.confidence,
        )
        action_requires_approval = requires_approval(action_plan.confidence, self.approval_threshold)
        if action_requires_approval:
            action_plan.status = "pending_approval"
            for plan_step in action_plan.steps:
                plan_step.status = "pending_approval"
            action.status = "pending_approval"
            self.queue.enqueue(asdict(action))
            set_stage(envelope, "waiting_approval")
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_WAITING_APPROVAL)
        else:
            action_plan.status = "approved"
            for plan_step in action_plan.steps:
                plan_step.status = "approved"
            action.status = "approved"
            set_stage(envelope, "action_done")
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)

        append_or_refine_section(envelope, agent_name="action_agent", section_value=action)
        envelope.action_plan = action_plan
        self.action_repo.upsert_action(run_id, deal_id, action)
        self.action_repo.upsert_action_plan(run_id, deal_id, action.action_id, action_plan)
        self._snapshot(deal_id, envelope, source_agent="action_agent")
        self.long_memory.add_outcome(
            OutcomeRecord(deal_id=deal_id, action_id=action.action_id, outcome_label="pending", insight="Action created")
        )
        return False

    def _handle_crm_agent_step(self, workflow_id: str, step: str, deal_id: str, run_id: str, envelope: ContextEnvelope) -> bool:
        crm_action_plan = self._execute_with_step_audit(
            workflow_id=workflow_id,
            step=step,
            fn=lambda: crm_agent(
                envelope.raw_data,
                envelope.deal_context,
                envelope.decision_context,
                workflow_id=workflow_id,
                run_id=run_id,
            ),
        )
        if not crm_action_plan.steps:
            raise ValueError("crm_agent returned an empty action plan")
        first_step = sorted(crm_action_plan.steps, key=lambda item: item.order)[0]
        action = ActionContext(
            action_id=first_step.step_id,
            type=first_step.action_type,
            subject=first_step.subject,
            preview=first_step.preview,
            body_draft=first_step.body_draft,
            status="approved",
            reasoning=crm_action_plan.reasoning,
            confidence=crm_action_plan.confidence,
        )
        crm_action_plan.status = "approved"
        for plan_step in crm_action_plan.steps:
            plan_step.status = "approved"
        append_or_refine_section(envelope, agent_name="crm_agent", section_value=action)
        envelope.action_plan = crm_action_plan
        set_stage(envelope, "action_done")
        self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
        self.action_repo.upsert_action(run_id, deal_id, action)
        self.action_repo.upsert_action_plan(run_id, deal_id, action.action_id, crm_action_plan)
        self._snapshot(deal_id, envelope, source_agent="crm_agent")
        outcome = self._outcome_from_raw_data(envelope.raw_data)
        self.resume_after_approval(envelope, outcome, workflow_id=workflow_id)
        return False

    def resume_after_approval(
        self,
        envelope: ContextEnvelope,
        outcome: ExecutionOutcome,
        *,
        workflow_id: str = "deal_followup_workflow",
    ) -> ContextEnvelope:
        action_ctx = envelope.action_context
        if action_ctx is None:
            raise ValueError("Missing action_context")
        action_ctx.status = "approved"
        action_plan = envelope.action_plan or ActionPlanContext(
            plan_id=f"plan-{action_ctx.action_id}",
            steps=[],
            status=action_ctx.status,
            reasoning=action_ctx.reasoning,
            confidence=action_ctx.confidence,
        )
        if not action_plan.steps:
            action_plan.steps.append(
                ActionStep(
                    step_id=action_ctx.action_id,
                    order=1,
                    channel="email",
                    action_type=action_ctx.type,
                    subject=action_ctx.subject,
                    preview=action_ctx.preview,
                    body_draft=action_ctx.body_draft,
                    status="approved",
                )
            )
        for plan_step in action_plan.steps:
            if plan_step.status != "executed":
                plan_step.status = "approved"
        action_plan.status = "approved"
        envelope.action_plan = action_plan

        run_id = self._run_ids.get(envelope.meta.deal_id)
        existing_execution = self.outcome_repo.get_execution(action_ctx.action_id)
        if existing_execution:
            executed_steps = {str(item["step_id"]): item for item in self.outcome_repo.list_execution_steps(action_ctx.action_id)}
            for plan_step in action_plan.steps:
                persisted = executed_steps.get(plan_step.step_id)
                if not persisted:
                    continue
                plan_step.status = str(persisted["status"])
                plan_step.retry_count = int(persisted["retry_count"] or 0)
                receipt = persisted.get("receipt_json")
                if isinstance(receipt, str) and receipt:
                    plan_step.execution_result = json.loads(receipt)
            if action_plan.steps and all(step.status == "executed" for step in action_plan.steps):
                return envelope

        try:
            execution = self._execute_with_step_audit(
                workflow_id="resume_after_approval",
                step="execution_agent",
                fn=lambda: execution_agent(
                    action_plan,
                    deal_id=envelope.meta.deal_id,
                    contact_name=envelope.raw_data.get("contact_name", "Prospect"),
                    workflow_id=workflow_id,
                    execution_phase="human_review",
                    run_id=run_id,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            if run_id:
                payload = self._serialize_error("resume_after_approval", "execution_agent", 0, exc)
                self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_FAILED, last_error=payload, complete=True)
            raise
        append_or_refine_section(envelope, agent_name="execution_agent", section_value=execution)
        set_stage(envelope, "execution_done")
        if run_id:
            self.outcome_repo.record_execution(run_id, envelope.meta.deal_id, action_ctx.action_id, execution)
            self.action_repo.upsert_action_plan(run_id, envelope.meta.deal_id, action_ctx.action_id, action_plan)
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_RUNNING)
            self._snapshot(envelope.meta.deal_id, envelope, source_agent="execution_agent")

        try:
            outcome_ctx = self._execute_with_step_audit(
                workflow_id="resume_after_approval",
                step="evaluator_agent",
                fn=lambda: evaluator_agent(
                    execution,
                    outcome,
                    workflow_id=workflow_id,
                    run_id=run_id,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            if run_id:
                payload = self._serialize_error("resume_after_approval", "evaluator_agent", 0, exc)
                self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_FAILED, last_error=payload, complete=True)
            raise
        append_or_refine_section(envelope, agent_name="evaluator_agent", section_value=outcome_ctx)
        set_stage(envelope, "evaluation_done")
        if run_id:
            self.outcome_repo.record_outcome(run_id, envelope.meta.deal_id, action_ctx.action_id, outcome_ctx)
            attach_prompt_outcome(run_id=run_id, outcome_label=outcome_ctx.outcome_label)
            attach_prompt_outcome_metrics(
                run_id=run_id,
                reply_received=outcome.reply_received,
                meeting_booked=outcome.meeting_booked,
                execution_success=execution.status == "executed",
            )
            persona = envelope.deal_context.persona if envelope.deal_context else "unknown"
            memory_insight = f"{outcome_ctx.insight} | {_memory_influence_summary(envelope)}"
            self.outcome_repo.add_persona_insight(persona, memory_insight, outcome_ctx.confidence)
            self._update_run_status(run_id, envelope.meta.workflow_stage, RUN_STATUS_COMPLETED, complete=True)
            self._snapshot(envelope.meta.deal_id, envelope, source_agent="evaluator_agent")

        self.long_memory.add_outcome(
            OutcomeRecord(
                deal_id=envelope.meta.deal_id,
                action_id=action_ctx.action_id,
                outcome_label=outcome_ctx.outcome_label,
                insight=f"{outcome_ctx.insight} | {_memory_influence_summary(envelope)}",
            )
        )
        self.short_memory.save(envelope.meta.deal_id, envelope)
        return envelope
