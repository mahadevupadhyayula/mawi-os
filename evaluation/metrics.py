"""
Purpose:
Evaluation module `metrics` for analyzing outcomes and generating learning signals.

Technical Details:
Calculates metrics/insights from execution traces and feeds feedback artifacts to memory for future decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class WorkflowMetrics:
    steps_completed: int
    approval_required: bool
    execution_status: str
    outcome_label: str


class WorkflowPathMetrics:
    """Baseline counters for run-status transitions used in operational debugging."""

    def __init__(self) -> None:
        self._counts = {
            "skipped": 0,
            "running": 0,
            "waiting_approval": 0,
            "completed": 0,
        }
        self._lock = Lock()

    def increment(self, status: str) -> None:
        if status not in self._counts:
            return
        with self._lock:
            self._counts[status] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)
