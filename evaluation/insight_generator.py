"""
Purpose:
Evaluation module `insight_generator` for analyzing outcomes and generating learning signals.

Technical Details:
Calculates metrics/insights from execution traces and feeds feedback artifacts to memory for future decisions.
"""

from __future__ import annotations


def generate_insight(outcome_label: str, strategy_type: str) -> str:
    if outcome_label == "positive":
        return f"{strategy_type} improved reply rate for similar deals."
    return f"{strategy_type} needs refinement or timing adjustment."
