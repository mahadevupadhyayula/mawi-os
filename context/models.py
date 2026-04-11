"""
Purpose:
Context module `models` used to model and manipulate workflow context envelopes.

Technical Details:
Defines typed structures/helpers that preserve stage-by-stage provenance and immutable-style context updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


ContextStatus = Literal["draft", "pending_approval", "approved", "rejected", "executed", "failed", "partial"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SectionMeta:
    version: int = 1
    source_agent: str = "system"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    parent_version: Optional[int] = None


@dataclass
class SectionBase:
    reasoning: str
    confidence: float
    meta: SectionMeta = field(default_factory=SectionMeta)


@dataclass
class SignalContext(SectionBase):
    stalled: bool = False
    days_since_reply: int = 0
    urgency: Literal["low", "medium", "high"] = "low"
    trigger_reason: str = ""


@dataclass
class DealContext(SectionBase):
    persona: str = "unknown"
    deal_stage: str = "unknown"
    known_objections: List[str] = field(default_factory=list)
    recent_timeline: List[str] = field(default_factory=list)
    recommended_tone: str = "professional"


@dataclass
class DecisionContext(SectionBase):
    strategy_id: str = ""
    strategy_type: str = ""
    message_goal: str = ""
    fallback_strategy: str = ""


@dataclass
class ActionContext(SectionBase):
    action_id: str = ""
    type: str = "send_email"
    subject: str = ""
    preview: str = ""
    body_draft: str = ""
    status: ContextStatus = "draft"


@dataclass
class ExecutionContext(SectionBase):
    execution_id: str = ""
    status: ContextStatus = "draft"
    email_result: Dict[str, Any] = field(default_factory=dict)
    crm_result: Dict[str, Any] = field(default_factory=dict)
    tool_events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OutcomeContext(SectionBase):
    outcome_label: str = ""
    insight: str = ""
    recommended_adjustment: str = ""


@dataclass
class MetaContext:
    deal_id: str
    timestamp: str = field(default_factory=utc_now_iso)
    workflow_stage: str = "initialized"


@dataclass
class ContextEnvelope:
    meta: MetaContext
    signal_context: Optional[SignalContext] = None
    deal_context: Optional[DealContext] = None
    decision_context: Optional[DecisionContext] = None
    action_context: Optional[ActionContext] = None
    execution_context: Optional[ExecutionContext] = None
    outcome_context: Optional[OutcomeContext] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
