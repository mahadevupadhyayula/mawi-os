"""
Purpose:
Evaluation module `metrics` for analyzing outcomes and generating learning signals.

Technical Details:
Calculates metrics/insights from execution traces and feeds feedback artifacts to memory for future decisions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkflowMetrics:
    steps_completed: int
    approval_required: bool
    execution_status: str
    outcome_label: str
