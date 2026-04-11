"""Request/response schemas for the web transport adapter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StartWorkflowRequest(BaseModel):
    deal_id: str = Field(..., description="Deal identifier used to run workflow orchestration.")


class WorkflowSelectionMixin(BaseModel):
    workflow: str = Field(
        default="deal-followup",
        description="Route-level workflow selector. Supports 'deal-followup' alias and registered workflow IDs.",
    )


class StartWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class ActionListResponse(BaseModel):
    actions: list[dict[str, Any]]


class ApproveActionRequest(WorkflowSelectionMixin):
    action_id: str
    approver: str
    reply_received: bool = True
    meeting_booked: bool = False


class RejectActionRequest(WorkflowSelectionMixin):
    action_id: str
    approver: str
    reason: str


class EditActionRequest(WorkflowSelectionMixin):
    action_id: str
    approver: str
    preview: str | None = None
    body_draft: str | None = None


class ActionMutationResponse(BaseModel):
    status: str
    deal_id: str
    action_id: str
    reason: str | None = None


class DealStateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class RunSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Stable error type for API clients.")
    message: str = Field(..., description="Human-readable description for debugging and display.")
