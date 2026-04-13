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
from agents.prompt_templates import attach_prompt_rejection, get_prompt_diagnostics_report
from approval.action_lifecycle import approve, edit, reject
from context.models import (
    ActionContext,
    ActionPlanContext,
    ActionStep,
    ContextEnvelope,
    DealContext,
    DecisionContext,
    ExecutionContext,
    MetaContext,
    OutcomeContext,
    SectionMeta,
    SignalContext,
)
from data.repositories import CRMSyncLogRepository, InterventionLogRepository
from orchestrator.runner import WorkflowOrchestrator
from workflows.registry import get_registered_workflow_names, is_known_workflow


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
        self.intervention_log_repo = InterventionLogRepository(db=self.orchestrator.workflow_repo.db)
        self.crm_sync_log_repo = CRMSyncLogRepository(db=self.orchestrator.workflow_repo.db)

    def start_workflow(
        self,
        deal_id: str,
        workflow_name: str | None = None,
        *,
        trigger_context: dict[str, Any] | None = None,
    ) -> dict:
        if workflow_name is not None and not is_known_workflow(workflow_name):
            supported = ", ".join(get_registered_workflow_names())
            raise ValueError(f"Unknown workflow name: {workflow_name}. Supported workflows: {supported}")

        envelope = self.orchestrator.run_workflow(
            deal_id,
            workflow_name=workflow_name,
            trigger_context=trigger_context,
        )
        self._deal_envelopes[deal_id] = envelope
        return asdict(envelope)

    def get_actions(self, status: str | None = None) -> List[dict]:
        desired_status = status or "pending_approval"
        persisted = self.orchestrator.action_repo.list_actions(desired_status)
        if persisted:
            return persisted
        return self.orchestrator.queue.list_actions(status=desired_status)

    def approve_action(
        self,
        action_id: str,
        approver: str,
        *,
        step_id: str | None = None,
        reply_received: bool = True,
        meeting_booked: bool = False,
    ) -> dict:
        action = self._get_action(action_id)
        updated = approve(action, approver)
        self.orchestrator.queue.enqueue(updated)
        self.orchestrator.action_repo.set_approved(action_id, approver, step_id=step_id)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._load_envelope(deal_id)
        if step_id is None:
            envelope.action_context.status = "approved"
        if envelope.action_plan:
            if step_id is None:
                envelope.action_plan.status = "approved"
                for step in envelope.action_plan.steps:
                    step.status = "approved"
            else:
                for step in envelope.action_plan.steps:
                    if step.step_id == step_id:
                        step.status = "approved"
                if envelope.action_plan.steps and all(step.status == "approved" for step in envelope.action_plan.steps):
                    envelope.action_plan.status = "approved"
        outcome = ExecutionOutcome(reply_received=reply_received, meeting_booked=meeting_booked)
        resumed = self.orchestrator.resume_after_approval(envelope, outcome)
        self._deal_envelopes[deal_id] = resumed
        return {"status": "approved", "deal_id": deal_id, "action_id": action_id, "step_id": step_id}

    def reject_action(self, action_id: str, approver: str, reason: str, *, step_id: str | None = None) -> dict:
        action = self._get_action(action_id)
        updated = reject(action, approver, reason)
        self.orchestrator.queue.enqueue(updated)
        self.orchestrator.action_repo.set_rejected(action_id, approver, reason, step_id=step_id)
        attach_prompt_rejection(action_id=action_id)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._load_envelope(deal_id)
        if step_id is None:
            envelope.action_context.status = "rejected"
        if envelope.action_plan:
            if step_id is None:
                envelope.action_plan.status = "rejected"
                for step in envelope.action_plan.steps:
                    step.status = "rejected"
            else:
                for step in envelope.action_plan.steps:
                    if step.step_id == step_id:
                        step.status = "rejected"
        self._deal_envelopes[deal_id] = envelope
        return {"status": "rejected", "deal_id": deal_id, "action_id": action_id, "step_id": step_id, "reason": reason}

    def edit_action(
        self,
        action_id: str,
        approver: str,
        *,
        step_id: str | None = None,
        preview: str | None = None,
        body_draft: str | None = None,
    ) -> dict:
        action = self._get_action(action_id)
        updated = edit(action, approver, preview=preview, body_draft=body_draft)
        self.orchestrator.queue.enqueue(updated)
        self.orchestrator.action_repo.set_edited(action_id, approver, preview, body_draft, step_id=step_id)

        deal_id = self._find_deal_for_action(action_id)
        envelope = self._load_envelope(deal_id)
        if preview is not None:
            envelope.action_context.preview = preview
        if body_draft is not None:
            envelope.action_context.body_draft = body_draft
        if step_id is None:
            envelope.action_context.status = "pending_approval"
        if envelope.action_plan and envelope.action_plan.steps:
            envelope.action_plan.status = "pending_approval"
            target_step = None
            if step_id is not None:
                target_step = next((step for step in envelope.action_plan.steps if step.step_id == step_id), None)
            if target_step is None:
                target_step = sorted(envelope.action_plan.steps, key=lambda step: step.order)[0]
            if preview is not None:
                target_step.preview = preview
            if body_draft is not None:
                target_step.body_draft = body_draft
            target_step.status = "pending_approval"
        self._deal_envelopes[deal_id] = envelope
        return {"status": "edited", "deal_id": deal_id, "action_id": action_id, "step_id": step_id}

    def get_deal_state(self, deal_id: str) -> dict:
        envelope = self._deal_envelopes.get(deal_id)
        if envelope is not None:
            return asdict(envelope)

        persisted = self.orchestrator.workflow_repo.get_latest_envelope(deal_id)
        if persisted is not None:
            return persisted

        raise ValueError("Deal state not found")

    def get_run_summary(self, *, deal_id: str | None = None, run_id: str | None = None) -> dict:
        summary = self.orchestrator.workflow_repo.get_run_summary(run_id=run_id, deal_id=deal_id)
        if summary is None:
            raise ValueError("Run summary not found")
        summary["path_metrics"] = self.orchestrator.path_metrics.snapshot()
        summary["feedback_metrics"] = self.orchestrator.feedback_metrics.snapshot()
        return summary

    def get_prompt_diagnostics(self, *, limit: int = 25) -> dict:
        return get_prompt_diagnostics_report(limit=limit)

    def run_intervention_workflow(self, deal_id: str) -> dict[str, str | None]:
        workflow_id = "deal_intervention_workflow"
        envelope = self.orchestrator.run_workflow(deal_id, workflow_name=workflow_id)
        self._deal_envelopes[deal_id] = envelope
        run_id = self.orchestrator.workflow_repo.get_latest_run_id(deal_id)
        self.intervention_log_repo.insert_log(
            run_id=run_id or "unknown",
            deal_id=deal_id,
            intervention_type="automated",
            status="completed",
            details={"workflow_stage": envelope.meta.workflow_stage, "workflow_id": workflow_id},
        )
        return self._workflow_run_envelope(
            workflow_id=workflow_id,
            deal_id=deal_id,
            run_id=run_id,
            workflow_stage=envelope.meta.workflow_stage,
        )

    def run_crm_sync_workflow(self, deal_id: str) -> dict[str, str | None]:
        workflow_id = "crm_sync_workflow"
        envelope = self.orchestrator.run_workflow(
            deal_id,
            workflow_name=workflow_id,
            trigger_context={"trigger_source": "api", "trigger_event": "explicit"},
        )
        self._deal_envelopes[deal_id] = envelope
        run_id = self.orchestrator.workflow_repo.get_latest_run_id(deal_id)
        self.crm_sync_log_repo.insert_log(
            run_id=run_id or "unknown",
            deal_id=deal_id,
            sync_status="completed",
            request={"source": "api", "workflow_id": workflow_id},
            response={"workflow_stage": envelope.meta.workflow_stage},
            synced_at=envelope.meta.updated_at,
        )
        return self._workflow_run_envelope(
            workflow_id=workflow_id,
            deal_id=deal_id,
            run_id=run_id,
            workflow_stage=envelope.meta.workflow_stage,
        )

    def get_crm_sync_status(self, *, deal_id: str | None = None, run_id: str | None = None) -> dict[str, str | None]:
        if run_id is None and deal_id is None:
            raise ValueError("Either run_id or deal_id must be provided")

        rows = self.crm_sync_log_repo.list_logs(run_id=run_id, deal_id=deal_id, limit=1)
        if rows:
            latest = rows[0]
            return {
                "status": "ok",
                "deal_id": str(latest.get("deal_id")) if latest.get("deal_id") is not None else None,
                "run_id": str(latest.get("run_id")) if latest.get("run_id") is not None else None,
                "sync_status": str(latest.get("sync_status") or "unknown"),
                "synced_at": str(latest.get("synced_at")) if latest.get("synced_at") else None,
                "error_message": str(latest.get("error_message")) if latest.get("error_message") else None,
                "updated_at": str(latest.get("updated_at")) if latest.get("updated_at") else None,
            }

        return {
            "status": "ok",
            "deal_id": deal_id,
            "run_id": run_id,
            "sync_status": "not_started",
            "synced_at": None,
            "error_message": None,
            "updated_at": None,
        }

    def _workflow_run_envelope(
        self,
        *,
        workflow_id: str,
        deal_id: str,
        run_id: str | None,
        workflow_stage: str,
    ) -> dict[str, str | None]:
        return {
            "status": "started",
            "workflow_id": workflow_id,
            "deal_id": deal_id,
            "run_id": run_id,
            "workflow_stage": workflow_stage,
        }

    def _get_action(self, action_id: str) -> dict:
        action = self.orchestrator.queue.get(action_id)
        if action:
            return action
        action = self.orchestrator.action_repo.get_action(action_id)
        if action:
            return action
        raise ValueError("Action not found")

    def _find_deal_for_action(self, action_id: str) -> str:
        for deal_id, envelope in self._deal_envelopes.items():
            if envelope.action_context and envelope.action_context.action_id == action_id:
                return deal_id

        persisted = self.orchestrator.action_repo.get_action(action_id)
        if persisted and persisted.get("deal_id"):
            return str(persisted["deal_id"])
        raise ValueError("Deal for action not found")

    def _load_envelope(self, deal_id: str) -> ContextEnvelope:
        envelope = self._deal_envelopes.get(deal_id)
        if envelope is not None:
            return envelope

        persisted = self.orchestrator.workflow_repo.get_latest_envelope(deal_id)
        if persisted is None:
            raise ValueError("Deal state not found")
        hydrated = self._hydrate_envelope(persisted)
        run_id = self.orchestrator.workflow_repo.get_latest_run_id(deal_id)
        if run_id:
            self.orchestrator._run_ids[deal_id] = run_id
        self._deal_envelopes[deal_id] = hydrated
        return hydrated

    def _hydrate_envelope(self, payload: dict) -> ContextEnvelope:
        def hydrate_meta(value: dict | None) -> SectionMeta:
            if not value:
                return SectionMeta()
            return SectionMeta(**value)

        def hydrate(section_cls: Any, value: dict | None) -> Any:
            if value is None:
                return None
            data = dict(value)
            data["meta"] = hydrate_meta(data.get("meta"))
            return section_cls(**data)

        return ContextEnvelope(
            meta=MetaContext(**payload.get("meta", {})),
            signal_context=hydrate(SignalContext, payload.get("signal_context")),
            deal_context=hydrate(DealContext, payload.get("deal_context")),
            decision_context=hydrate(DecisionContext, payload.get("decision_context")),
            action_context=hydrate(ActionContext, payload.get("action_context")),
            action_plan=self._hydrate_action_plan(payload.get("action_plan")),
            execution_context=hydrate(ExecutionContext, payload.get("execution_context")),
            outcome_context=hydrate(OutcomeContext, payload.get("outcome_context")),
            raw_data=payload.get("raw_data", {}),
            history=payload.get("history", []),
        )

    def _hydrate_action_step(self, value: dict) -> ActionStep:
        return ActionStep(**value)

    def _hydrate_action_plan(self, value: dict | None) -> ActionPlanContext | None:
        if value is None:
            return None
        data = dict(value)
        data["meta"] = SectionMeta(**data.get("meta", {}))
        data["steps"] = [self._hydrate_action_step(item) for item in data.get("steps", [])]
        return ActionPlanContext(**data)
