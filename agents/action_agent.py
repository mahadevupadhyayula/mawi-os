from __future__ import annotations

from uuid import uuid4

from context.merge_rules import append_or_refine
from context.schemas import ActionStatus, AgentSection, ContextEnvelope


def action_agent(envelope: ContextEnvelope) -> ContextEnvelope:
    deal = envelope.deal_context.current.structured if envelope.deal_context.current else {}
    decision = envelope.decision_context.current.structured if envelope.decision_context.current else {}
    subject = "Quick idea to unlock ROI this quarter"
    preview = (
        f"Hi {deal.get('persona', 'there')}, based on your {deal.get('deal_stage', 'evaluation')} stage, "
        "I can share a concise ROI model tailored to your current pipeline."
    )
    confidence = 0.72 if decision.get("strategy_type") == "roi_framing" else 0.65
    section = AgentSection(
        structured={
            "action_id": str(uuid4()),
            "type": "send_email",
            "subject": subject,
            "preview": preview,
            "body": preview + " Would you be open to a 15-minute review this week?",
            "channel": "email",
            "status": ActionStatus.PENDING_APPROVAL,
            "approval_required": True,
        },
        reasoning="Generated follow-up email aligned to selected strategy.",
        confidence=confidence,
    )
    envelope.meta.workflow_stage = "action_agent"
    return append_or_refine(envelope, "action_context", section)
