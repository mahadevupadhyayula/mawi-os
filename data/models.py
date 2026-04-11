"""
Purpose:
Data-layer model definitions and shared constants for persistence-backed workflow state.
"""

from __future__ import annotations

WORKFLOW_NAME = "deal_followup_workflow"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_WAITING_APPROVAL = "waiting_approval"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_SKIPPED = "skipped"
