"""
Purpose:
Agent module `execution_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

from uuid import uuid4

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from approval.policy import validate_step_channel_policy
from context.models import ActionPlanContext, ActionStep, ExecutionContext
from tools.crm_tool import update_crm
from tools.email_tool import send_email
from tools.sms_tool import send_sms


def _execute_step(step: ActionStep, *, deal_id: str, contact_name: str) -> dict:
    dispatch = {
        ("email", "send_email"): lambda: send_email(to_name=contact_name, subject=step.subject, body=step.body_draft),
        ("crm", "update_crm"): lambda: update_crm(deal_id=deal_id, note=step.body_draft, message_id=f"plan-step-{step.step_id}"),
        ("sms", "send_sms"): lambda: send_sms(to_name=contact_name, body=step.body_draft),
    }
    executor = dispatch.get((step.channel, step.action_type))
    if executor:
        return executor()
    return {"success": False, "error": "unsupported_step", "channel": step.channel, "action_type": step.action_type}


def execution_agent(
    action_plan: ActionPlanContext,
    *,
    deal_id: str,
    contact_name: str,
    allowed_channels: tuple[str, ...] = ("email", "crm", "sms"),
    max_risk_tier: str = "high",
) -> ExecutionContext:
    _ = render_prompt(
        "execution_prompt.txt",
        prompt_contract={
            "workflow_goal": "Execute approved action steps through channel adapters with policy enforcement.",
            "stage_name": "execution_agent",
            "policy_mode": "enforced",
            "output_model": ExecutionContext,
        },
    )
    if action_plan.status != "approved":
        return ExecutionContext(
            execution_id=str(uuid4()),
            status="failed",
            email_result={"success": False, "error": "action_plan_not_approved"},
            crm_result={},
            tool_events=[],
            reasoning="Execution blocked: action plan is not approved.",
            confidence=1.0,
        )

    ordered_steps = sorted(action_plan.steps, key=lambda step: step.order)
    tool_events: list[dict] = []
    step_results: list[dict] = []
    for step in ordered_steps:
        policy_decision = validate_step_channel_policy(
            step,
            allowed_channels=allowed_channels,
            max_risk_tier=max_risk_tier,
        )
        channel_metadata = {
            "policy": {
                "allowed_channels": list(allowed_channels),
                "max_risk_tier": max_risk_tier,
                "channel_risk_tier": policy_decision.risk_tier,
            }
        }
        if not policy_decision.allowed:
            receipt = {
                "success": False,
                "error": policy_decision.reason,
                "channel": policy_decision.channel,
                "risk_tier": policy_decision.risk_tier,
                "channel_metadata": channel_metadata,
            }
            event_type = "blocked_by_policy"
            step.retry_count += 1
            step.execution_result = receipt
            step.status = "failed"
            step.last_error = policy_decision.reason
            step_results.append(
                {
                    "step_id": step.step_id,
                    "order": step.order,
                    "channel": step.channel,
                    "action_type": step.action_type,
                    "status": step.status,
                    "retry_count": step.retry_count,
                    "receipt": receipt,
                }
            )
            tool_events.append(
                {
                    "step_id": step.step_id,
                    "order": step.order,
                    "tool": step.action_type,
                    "channel": step.channel,
                    "success": False,
                    "event_type": event_type,
                    "channel_metadata": channel_metadata,
                }
            )
            continue

        if step.status == "executed" and step.execution_result.get("success"):
            receipt = dict(step.execution_result)
            event_type = "already_executed"
        else:
            step.retry_count += 1
            receipt = _execute_step(step, deal_id=deal_id, contact_name=contact_name)
            event_type = "executed"
        step.execution_result = receipt
        if receipt.get("success"):
            step.status = "executed"
            step.last_error = ""
        else:
            step.status = "failed"
            step.last_error = str(receipt.get("error", "execution_failed"))
        step_results.append(
            {
                "step_id": step.step_id,
                "order": step.order,
                "channel": step.channel,
                "action_type": step.action_type,
                "status": step.status,
                "retry_count": step.retry_count,
                "receipt": receipt,
            }
        )
        receipt_metadata = receipt.get("channel_metadata", {})
        merged_channel_metadata = {**channel_metadata, **receipt_metadata}
        tool_events.append(
            {
                "step_id": step.step_id,
                "order": step.order,
                "tool": step.action_type,
                "channel": step.channel,
                "success": bool(receipt.get("success")),
                "event_type": event_type,
                "channel_metadata": merged_channel_metadata,
            }
        )
    all_success = all(evt["success"] for evt in tool_events) if tool_events else False
    any_success = any(evt["success"] for evt in tool_events)
    status = "executed" if all_success else ("partial" if any_success else "failed")
    reasoning = "Executed ordered action plan through channel-specific adapters."
    confidence = 0.88 if status == "executed" else 0.55

    email_receipt = next((item["receipt"] for item in step_results if item["channel"] == "email"), {})
    crm_receipt = next((item["receipt"] for item in step_results if item["channel"] == "crm"), {})
    sms_receipt = next((item["receipt"] for item in step_results if item["channel"] == "sms"), {})
    result = make_result(
        ExecutionContext(
            execution_id=str(uuid4()),
            status=status,
            email_result=email_receipt,
            crm_result=crm_receipt,
            tool_events=tool_events + [{"by_step": step_results, "channel_results": {"sms": sms_receipt}}],
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
