"""
Purpose:
Agent module `crm_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Builds a strict CRM sync action plan from normalized CRM state and deal context while keeping all side effects delegated to tool adapters.
"""

from __future__ import annotations

import json
from uuid import uuid4

from agents.contracts import make_result
from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from context.models import ActionPlanContext, ActionStep, DealContext, DecisionContext


def _normalize_crm_state(raw_data: dict) -> dict:
    crm_state = raw_data.get("crm_state")
    if not isinstance(crm_state, dict):
        crm_state = {}
    pending_updates = crm_state.get("pending_updates", raw_data.get("crm_pending_updates", []))
    if not isinstance(pending_updates, list):
        pending_updates = []

    return {
        "record_id": str(crm_state.get("record_id") or raw_data.get("crm_record_id") or ""),
        "last_synced_at": str(crm_state.get("last_synced_at") or raw_data.get("crm_last_synced_at") or ""),
        "pending_updates": [str(item) for item in pending_updates if item],
        "sync_required": bool(
            crm_state.get("sync_required", raw_data.get("crm_sync_required", False))
            or pending_updates
            or raw_data.get("trigger_event") == "post_action_execution"
        ),
    }


def crm_agent(
    raw_data: dict,
    deal_context: DealContext,
    decision_context: DecisionContext | None = None,
    *,
    workflow_id: str = "crm_sync_workflow",
    run_id: str | None = None,
) -> ActionPlanContext:
    _ = render_prompt(
        "action_prompt.txt",
        prompt_contract={
            "workflow_goal": "Generate an ordered CRM synchronization plan from normalized CRM state.",
            "stage_name": "crm_agent",
            "policy_mode": "policy_guided",
            "output_model": ActionPlanContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "crm_agent",
        },
    )

    crm_state = _normalize_crm_state(raw_data)
    pending_updates = crm_state["pending_updates"]
    if pending_updates:
        update_summary = "; ".join(pending_updates)
    else:
        update_summary = "Post-action CRM checkpoint and timeline sync"

    strategy = decision_context.strategy_type if decision_context else "context_only"
    reasoning = (
        "Normalized CRM state and built a CRM-only sync action plan for deterministic orchestrator execution. "
        f"strategy={strategy}; pending_updates={len(pending_updates)}; sync_required={crm_state['sync_required']}."
    )
    confidence = 0.86 if crm_state["sync_required"] else 0.68

    step = ActionStep(
        step_id=str(uuid4()),
        order=1,
        channel="crm",
        action_type="update_crm",
        preview="Sync latest outreach and deal signals into CRM record.",
        body_draft=(
            f"CRM sync for {deal_context.persona} at stage={deal_context.deal_stage}. "
            f"record_id={crm_state['record_id'] or 'unknown'}; updates={update_summary}."
        ),
        status="approved",
    )
    validation = validate_model_output_json(
        model_output=json.dumps(
            {
                "plan_id": str(uuid4()),
                "steps": [step.__dict__],
                "status": "approved",
                "reasoning": reasoning,
                "confidence": confidence,
            }
        ),
        required_json_fields=required_json_fields(ActionPlanContext),
        stage_name="crm_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"crm_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)

    result = make_result(
        ActionPlanContext(
            plan_id=str(payload["plan_id"]),
            steps=[step],
            status=str(payload["status"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
