"""
Purpose:
Implements the Action Agent that generates executable outreach content from decision and deal context.

Technical Details:
Uses prompt templates plus lightweight persona-aware rules to build structured ActionContext output consumable by approval and execution layers.
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


def _memory_signal_strength(decision_context: DecisionContext) -> float:
    return max(0.0, min(0.15, float(decision_context.memory_confidence_impact or 0.0)))


def _memory_backed_cta(decision_context: DecisionContext) -> str:
    if not decision_context.memory_evidence_used:
        return "If helpful, I can send a 2-point plan and timeline options."
    if _memory_signal_strength(decision_context) >= 0.08:
        return "If you're open, I can send two concrete options and hold a 15-minute slot this week."
    return "If helpful, I can share two concrete next-step options tailored to your rollout timeline."


def _subject_and_preview(decision_context: DecisionContext) -> tuple[str, str]:
    if not decision_context.memory_evidence_used:
        return (
            "Quick follow-up on your rollout goals",
            "Sharing a concise ROI angle tailored to your current stage.",
        )
    if decision_context.strategy_type == "roi_framing":
        return (
            "Follow-up: ROI path based on similar deals",
            "Memory-backed ROI signal suggests a concise business-case follow-up.",
        )
    return (
        "Follow-up: reducing rollout risk",
        "Memory-backed signal suggests a low-risk next-step message for this stage.",
    )


def action_agent(
    decision_context: DecisionContext,
    deal_context: DealContext,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> ActionPlanContext:
    prompt_text = render_prompt(
        "action_prompt.txt",
        prompt_contract={
            "workflow_goal": "Generate an ordered, approval-ready action plan from strategy and deal context.",
            "stage_name": "action_agent",
            "policy_mode": "policy_guided",
            "output_model": ActionPlanContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "action_agent",
        },
    )
    subject, preview = _subject_and_preview(decision_context)
    body = (
        f"Hi — following up with a short {decision_context.strategy_type.replace('_', ' ')} summary "
        f"for your {deal_context.deal_stage} stage. "
        f"{_memory_backed_cta(decision_context)}"
    )
    confidence = 0.74 if decision_context.strategy_type == "roi_framing" else 0.8
    reasoning = "Generated an ordered action plan with channel-specific steps."
    email_step = ActionStep(
        step_id=str(uuid4()),
        order=1,
        channel="email",
        action_type="send_email",
        subject=subject,
        preview=preview,
        body_draft=body,
        status="draft",
    )
    crm_preview = "Record ROI-focused follow-up in CRM timeline."
    crm_body = "Logged ROI framing follow-up and proposed timeline options."
    if decision_context.strategy_type != "roi_framing":
        crm_preview = "Record sequenced follow-up in CRM timeline."
        crm_body = "Logged sequenced follow-up and next-step timeline options."

    steps = [
        email_step,
        ActionStep(
            step_id=str(uuid4()),
            order=2,
            channel="crm",
            action_type="update_crm",
            preview=crm_preview,
            body_draft=crm_body,
            status="draft",
        ),
    ]
    deterministic_payload = {
        "plan_id": str(uuid4()),
        "steps": [step.__dict__ for step in steps],
        "status": "draft",
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(ActionPlanContext)
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    llm_enabled = runtime_config.enabled
    resolution = resolve_model_output(
        llm_enabled=llm_enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="action_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="action_agent",
        prompt_name="action_prompt.txt",
        llm_enabled=resolution.llm_enabled,
        provider=resolution.provider,
        model=resolution.model,
        llm_latency_ms=resolution.llm_latency_ms,
        token_usage=resolution.token_usage,
        fallback_reason=resolution.fallback_reason,
    )
    validation = validate_model_output_json(
        model_output=resolution.model_output,
        required_json_fields=required_fields,
        stage_name="action_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"action_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)

    hydrated_steps = _hydrate_action_steps(payload.get("steps"), stage_name="action_agent")
    selected_steps = steps if resolution.fallback_reason else hydrated_steps

    result = make_result(
        ActionPlanContext(
            plan_id=str(payload["plan_id"]),
            steps=selected_steps,
            status=str(payload["status"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
