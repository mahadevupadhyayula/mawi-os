from __future__ import annotations


def generate_insight(outcome_label: str, strategy_type: str) -> str:
    if outcome_label == "positive":
        return f"{strategy_type} improved reply rate for similar deals."
    return f"{strategy_type} needs refinement or timing adjustment."
