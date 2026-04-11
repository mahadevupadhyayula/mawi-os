"""FastAPI transport adapter for ``WorkflowAPI`` service methods."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from api.schemas import (
    ActionListResponse,
    ActionMutationResponse,
    ApproveActionRequest,
    DealStateResponse,
    EditActionRequest,
    ErrorResponse,
    RejectActionRequest,
    StartWorkflowRequest,
    StartWorkflowResponse,
)
from api.service import WorkflowAPI
from workflows.registry import is_known_workflow

router = APIRouter(prefix="/api", tags=["workflow"])

_WORKFLOW_ALIASES = {
    "deal-followup": "deal_followup_workflow",
}

_service = WorkflowAPI()

_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Unknown workflow."},
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Requested action or deal state could not be found.",
    },
}


def get_service() -> WorkflowAPI:
    return _service


def _error_response(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorResponse(error=error, message=message).model_dump())


def _resolve_workflow_name(workflow: str) -> str:
    resolved = _WORKFLOW_ALIASES.get(workflow, workflow)
    if not is_known_workflow(resolved):
        raise ValueError(f"Unknown workflow name: {workflow}")
    return resolved


@router.post(
    "/workflows/start",
    response_model=StartWorkflowResponse,
    responses=_ERROR_RESPONSES,
    summary="Start a workflow run for a deal",
)
def start_workflow(
    payload: StartWorkflowRequest,
    workflow: str = Query(default="deal-followup", description="Workflow id or alias"),
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, Any] | JSONResponse:
    try:
        selected_workflow = _resolve_workflow_name(workflow)
        return service.start_workflow(payload.deal_id, workflow_name=selected_workflow)
    except ValueError as exc:
        return _error_response(status.HTTP_400_BAD_REQUEST, "unknown_workflow", str(exc))


@router.get("/actions", response_model=ActionListResponse, summary="List actions by status")
def get_actions(
    status_filter: str | None = Query(default=None, alias="status"),
    service: WorkflowAPI = Depends(get_service),
) -> ActionListResponse:
    actions = service.get_actions(status=status_filter)
    return ActionListResponse(actions=actions)


@router.post(
    "/actions/approve",
    response_model=ActionMutationResponse,
    responses=_ERROR_RESPONSES,
    summary="Approve an action",
)
def approve_action(
    payload: ApproveActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str | None] | JSONResponse:
    try:
        _ = _resolve_workflow_name(payload.workflow)
        return service.approve_action(
            payload.action_id,
            payload.approver,
            reply_received=payload.reply_received,
            meeting_booked=payload.meeting_booked,
        )
    except ValueError as exc:
        message = str(exc)
        if "Unknown workflow" in message:
            return _error_response(status.HTTP_400_BAD_REQUEST, "unknown_workflow", message)
        return _error_response(status.HTTP_404_NOT_FOUND, "action_not_found", message)


@router.post(
    "/actions/reject",
    response_model=ActionMutationResponse,
    responses=_ERROR_RESPONSES,
    summary="Reject an action",
)
def reject_action(
    payload: RejectActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str | None] | JSONResponse:
    try:
        _ = _resolve_workflow_name(payload.workflow)
        return service.reject_action(payload.action_id, payload.approver, payload.reason)
    except ValueError as exc:
        message = str(exc)
        if "Unknown workflow" in message:
            return _error_response(status.HTTP_400_BAD_REQUEST, "unknown_workflow", message)
        return _error_response(status.HTTP_404_NOT_FOUND, "action_not_found", message)


@router.post(
    "/actions/edit",
    response_model=ActionMutationResponse,
    responses=_ERROR_RESPONSES,
    summary="Edit an action and reset it to pending approval",
)
def edit_action(
    payload: EditActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str | None] | JSONResponse:
    try:
        _ = _resolve_workflow_name(payload.workflow)
        return service.edit_action(
            payload.action_id,
            payload.approver,
            preview=payload.preview,
            body_draft=payload.body_draft,
        )
    except ValueError as exc:
        message = str(exc)
        if "Unknown workflow" in message:
            return _error_response(status.HTTP_400_BAD_REQUEST, "unknown_workflow", message)
        return _error_response(status.HTTP_404_NOT_FOUND, "action_not_found", message)


@router.get(
    "/deals/{deal_id}",
    response_model=DealStateResponse,
    responses=_ERROR_RESPONSES,
    summary="Fetch latest known state for a deal",
)
def get_deal_state(deal_id: str, service: WorkflowAPI = Depends(get_service)) -> dict[str, Any] | JSONResponse:
    try:
        return service.get_deal_state(deal_id)
    except ValueError as exc:
        return _error_response(status.HTTP_404_NOT_FOUND, "deal_state_not_found", str(exc))
