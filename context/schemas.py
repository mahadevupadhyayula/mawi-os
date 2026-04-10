from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AgentSection:
    structured: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.0
    agent_version: str = "v1"
    timestamp: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class MetaContext:
    deal_id: str
    workflow_run_id: str
    timestamp: datetime = field(default_factory=utcnow)
    workflow_stage: str = "triggered"


@dataclass
class SectionHistory:
    current: Optional[AgentSection] = None
    history: List[AgentSection] = field(default_factory=list)


@dataclass
class ContextEnvelope:
    meta: MetaContext
    signal_context: SectionHistory = field(default_factory=SectionHistory)
    deal_context: SectionHistory = field(default_factory=SectionHistory)
    decision_context: SectionHistory = field(default_factory=SectionHistory)
    action_context: SectionHistory = field(default_factory=SectionHistory)
    execution_context: SectionHistory = field(default_factory=SectionHistory)
    outcome_context: SectionHistory = field(default_factory=SectionHistory)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActionStatus:
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVED_WITH_EDITS = "approved_with_edits"
    EXECUTED = "executed"


@dataclass
class ActionObject:
    action_id: str
    preview: str
    confidence: float
    deal_id: str
    type: Literal["send_email"] = "send_email"
    status: str = ActionStatus.PENDING_APPROVAL
    editable_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutcomeSignal:
    deal_id: str
    action_id: Optional[str] = None
    replied: bool = False
    meeting_booked: bool = False
    response_latency_days: Optional[int] = None
    notes: str = ""
