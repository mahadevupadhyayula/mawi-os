from __future__ import annotations

from uuid import uuid4

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import ActionContext, ExecutionContext
from tools.crm_tool import update_crm
from tools.email_tool import send_email


def execution_agent(action_context: ActionContext, *, deal_id: str, contact_name: str) -> ExecutionContext:
    _ = render_prompt("execution_prompt.txt")
    if action_context.status != "approved":
        return ExecutionContext(
            execution_id=str(uuid4()),
            status="failed",
            email_result={"success": False, "error": "action_not_approved"},
            crm_result={},
            tool_events=[],
            reasoning="Execution blocked: action is not approved.",
            confidence=1.0,
        )

    email_receipt = send_email(to_name=contact_name, subject=action_context.subject, body=action_context.body_draft)
    crm_receipt = update_crm(
        deal_id=deal_id,
        note=f"Follow-up email sent. message_id={email_receipt['message_id']}",
        message_id=email_receipt["message_id"],
    )
    status = "executed" if email_receipt.get("success") and crm_receipt.get("success") else "partial"
    reasoning = "Executed send_email and update_crm through simulated tool adapters."
    confidence = 0.88 if status == "executed" else 0.55

    result = make_result(
        ExecutionContext(
            execution_id=str(uuid4()),
            status=status,
            email_result=email_receipt,
            crm_result=crm_receipt,
            tool_events=[
                {"tool": "send_email", "success": bool(email_receipt.get("success"))},
                {"tool": "update_crm", "success": bool(crm_receipt.get("success"))},
            ],
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
