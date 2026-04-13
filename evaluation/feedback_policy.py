"""
Purpose:
Evaluation policy module for memory-feedback quality gates and adaptation summaries.

Technical Details:
Keeps stage-specific adaptation rules deterministic and centralized so orchestrator logic stays
small and workflow behavior remains auditable.
"""

from __future__ import annotations

from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def gate_memory_evidence(*, stage: int, evidence: list[dict]) -> tuple[list[dict], str]:
    """
    Return evidence allowed for adaptation and a reason string.

    Stages:
    - 1: pass-through (basic enablement)
    - 2: require at least one medium/high quality memory item
    - 3: require at least two items with a stronger average quality signal
    """
    if stage <= 1:
        return evidence, "stage_1_basic_pass_through"

    qualities = [_as_float(item.get("quality_score")) for item in evidence if isinstance(item, dict)]
    if not qualities:
        return [], f"stage_{stage}_blocked_no_quality_items"

    if stage == 2:
        if max(qualities) < 0.2:
            return [], "stage_2_blocked_low_peak_quality"
        return evidence, "stage_2_pass_quality_gate"

    # stage >= 3 (strict)
    avg_quality = sum(qualities) / len(qualities)
    if len(qualities) < 2:
        return [], "stage_3_blocked_insufficient_items"
    if avg_quality < 0.25:
        return [], "stage_3_blocked_low_average_quality"
    return evidence, "stage_3_pass_quality_gate"


def summarize_adaptation(
    *,
    stage: int,
    selected_evidence: list[dict],
    gate_reason: str,
) -> dict[str, Any]:
    quality_scores = [
        _as_float(item.get("quality_score"))
        for item in selected_evidence
        if isinstance(item, dict)
    ]
    avg_quality = round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0.0
    return {
        "stage": stage,
        "gate_reason": gate_reason,
        "selected_items": len(selected_evidence),
        "avg_quality_score": avg_quality,
        "adaptation_enabled": bool(selected_evidence),
    }
