"""
Purpose:
Agent module `crm_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Builds a strict CRM sync action plan from normalized CRM state and deal context while keeping all side effects delegated to tool adapters.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from agents.contracts import make_result
from agents.inference import resolve_model_output
from agents.prompt_templates import (
    PromptLintError,
    attach_prompt_run_metadata,
    render_prompt,
    required_json_fields,
    validate_model_output_json,
)
from agents.runtime_config import load_runtime_llm_config
from context.models import ActionPlanContext, ActionStep, DealContext, DecisionContext

LOGGER = logging.getLogger(__name__)

_VALID_CHANNELS = {"email", "crm", "sms"}
_VALID_STATUSES = {"draft", "pending_approval", "approved", "rejected", "executed", "failed", "partial"}


def _hydrate_action_steps(payload_steps: object, *, stage_name: str) -> list[ActionStep]:
    if not isinstance(payload_steps, list):
        raise PromptLintError(f"{stage_name} output failed validation: ['steps must be a list']")

    hydrated_steps: list[ActionStep] = []
    required_step_fields = ("step_id", "order", "channel", "action_type")
    for index, raw_step in enumerate(payload_steps):
        if not isinstance(raw_step, dict):
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}] must be an object']"
            )
        missing = [field for field in required_step_fields if field not in raw_step]
        if missing:
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}] missing required fields: {missing}']"
            )
        step_id = raw_step["step_id"]
        order = raw_step["order"]
        channel = raw_step["channel"]
        action_type = raw_step["action_type"]
        status = raw_step.get("status", "draft")
        retry_count = raw_step.get("retry_count", 0)
        execution_result = raw_step.get("execution_result", {})
        if not isinstance(step_id, str) or not step_id:
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].step_id must be a non-empty string']"
            )
        if isinstance(order, bool) or not isinstance(order, int):
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].order must be an integer']"
            )
        if not isinstance(channel, str) or channel not in _VALID_CHANNELS:
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].channel must be one of {_VALID_CHANNELS}']"
            )
        if not isinstance(action_type, str) or not action_type:
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].action_type must be a non-empty string']"
            )
        if not isinstance(status, str) or status not in _VALID_STATUSES:
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].status must be one of {_VALID_STATUSES}']"
            )
        if isinstance(retry_count, bool) or not isinstance(retry_count, int):
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].retry_count must be an integer']"
            )
        if not isinstance(execution_result, dict):
            raise PromptLintError(
                f"{stage_name} output failed validation: ['steps[{index}].execution_result must be an object']"
            )
        hydrated_steps.append(
            ActionStep(
                step_id=step_id,
                order=order,
                channel=channel,
                action_type=action_type,
                subject=str(raw_step.get("subject", "")),
                preview=str(raw_step.get("preview", "")),
                body_draft=str(raw_step.get("body_draft", "")),
                status=status,
                retry_count=retry_count,
                execution_result=execution_result,
                last_error=str(raw_step.get("last_error", "")),
            )
        )

    return sorted(hydrated_steps, key=lambda step: step.order)

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
    prompt_text = render_prompt(
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
    deterministic_payload = {
        "plan_id": str(uuid4()),
        "steps": [step.__dict__],
        "status": "approved",
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(ActionPlanContext)
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    resolution = resolve_model_output(
        llm_enabled=runtime_config.enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="crm_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        max_retries=runtime_config.max_retries,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="crm_agent",
        prompt_name="action_prompt.txt",
        llm_enabled=resolution.llm_enabled,
        provider=resolution.provider,
        model=resolution.model,
        llm_latency_ms=resolution.llm_latency_ms,
        token_usage=resolution.token_usage,
        redaction_occurred=resolution.redaction_occurred,
        fallback_reason=resolution.fallback_reason,
    )
    validation = validate_model_output_json(
        model_output=resolution.model_output,
        required_json_fields=required_fields,
        stage_name="crm_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"crm_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    final_reasoning = str(payload["reasoning"])
    final_confidence = float(payload["confidence"])

    hydrated_steps = _hydrate_action_steps(payload.get("steps"), stage_name="crm_agent")
    selected_steps = [step] if resolution.fallback_reason else hydrated_steps

    result = make_result(
        ActionPlanContext(
            plan_id=str(payload["plan_id"]),
            steps=selected_steps,
            status=str(payload["status"]),
            reasoning=final_reasoning,
            confidence=final_confidence,
        ),
        final_reasoning,
        final_confidence,
    )
    return result.payload
