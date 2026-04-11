"""FastAPI transport adapter for ``WorkflowAPI`` service methods."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import (
    ActionListResponse,
    ActionMutationResponse,
    ApproveActionRequest,
    DealStateResponse,
    EditActionRequest,
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


def get_service() -> WorkflowAPI:
    return _service


def _resolve_workflow_name(workflow: str) -> str:
    resolved = _WORKFLOW_ALIASES.get(workflow, workflow)
    if not is_known_workflow(resolved):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown workflow name: {workflow}",
        )
    return resolved


@router.post("/workflows/start", response_model=StartWorkflowResponse)
def start_workflow(
    payload: StartWorkflowRequest,
    workflow: str = Query(default="deal-followup", description="Workflow id or alias"),
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, Any]:
    selected_workflow = _resolve_workflow_name(workflow)
    try:
        return service.start_workflow(payload.deal_id, workflow_name=selected_workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/actions", response_model=ActionListResponse)
def get_actions(
    status_filter: str | None = Query(default=None, alias="status"),
    service: WorkflowAPI = Depends(get_service),
) -> ActionListResponse:
    actions = service.get_actions(status=status_filter)
    return ActionListResponse(actions=actions)


@router.post("/actions/approve", response_model=ActionMutationResponse)
def approve_action(
    payload: ApproveActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str]:
    _ = _resolve_workflow_name(payload.workflow)
    try:
        return service.approve_action(
            payload.action_id,
            payload.approver,
            reply_received=payload.reply_received,
            meeting_booked=payload.meeting_booked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/actions/reject", response_model=ActionMutationResponse)
def reject_action(
    payload: RejectActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str]:
    _ = _resolve_workflow_name(payload.workflow)
    try:
        return service.reject_action(payload.action_id, payload.approver, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/actions/edit", response_model=ActionMutationResponse)
def edit_action(
    payload: EditActionRequest,
    service: WorkflowAPI = Depends(get_service),
) -> dict[str, str]:
    _ = _resolve_workflow_name(payload.workflow)
    try:
        return service.edit_action(
            payload.action_id,
            payload.approver,
            preview=payload.preview,
            body_draft=payload.body_draft,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/deals/{deal_id}", response_model=DealStateResponse)
def get_deal_state(deal_id: str, service: WorkflowAPI = Depends(get_service)) -> dict[str, Any]:
    try:
        return service.get_deal_state(deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
