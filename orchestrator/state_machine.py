from __future__ import annotations


STAGES = {
    "initialized",
    "signal_done",
    "context_done",
    "strategy_done",
    "action_done",
    "waiting_approval",
    "execution_done",
    "evaluation_done",
}


def is_valid_stage(stage: str) -> bool:
    return stage in STAGES
