from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkflowMetrics:
    steps_completed: int
    approval_required: bool
    execution_status: str
    outcome_label: str
