from __future__ import annotations

from context.merge_rules import append_or_refine
from context.schemas import ActionStatus, AgentSection, ContextEnvelope
from tools.crm_tool import update_crm
from tools.email_tool import send_email


def execution_agent(envelope: ContextEnvelope) -> ContextEnvelope:
    action = envelope.action_context.current
    if not action:
        raise ValueError("Missing action context")

    a = action.structured
    if a.get("status") not in {ActionStatus.APPROVED, ActionStatus.APPROVED_WITH_EDITS}:
        section = AgentSection(
            structured={
                "executed": False,
                "reason": "Awaiting human approval",
                "action_id": a.get("action_id"),
            },
            reasoning="Execution skipped because action not approved yet.",
            confidence=0.95,
        )
        envelope.meta.workflow_stage = "execution_agent_blocked"
        return append_or_refine(envelope, "execution_context", section)

    email_receipt = send_email(subject=a["subject"], body=a["body"], to=envelope.raw_data.get("contact_email", "test@example.com"))
    crm_receipt = update_crm(envelope.meta.deal_id, {"last_action_id": a["action_id"], "status": "followup_sent"})

    section = AgentSection(
        structured={
            "executed": True,
            "action_id": a["action_id"],
            "email_receipt": email_receipt,
            "crm_receipt": crm_receipt,
        },
        reasoning="Executed approved email and wrote execution trace to CRM.",
        confidence=0.9,
    )
    envelope.meta.workflow_stage = "execution_agent"
    return append_or_refine(envelope, "execution_context", section)
