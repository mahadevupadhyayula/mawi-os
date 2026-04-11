"""
Purpose:
Approval module `policy` for human review and action lifecycle control.

Technical Details:
Encodes approval states/policies and transitions so orchestrator resumes execution only after validated decisions.
"""

from __future__ import annotations


def requires_approval(confidence: float, threshold: float) -> bool:
    return confidence < threshold
