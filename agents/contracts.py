"""
Purpose:
Agent module `contracts` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentResult:
    payload: Any
    reasoning: str
    confidence: float
    warnings: list[str] | None = None


@dataclass
class ExecutionOutcome:
    reply_received: bool
    meeting_booked: bool
    notes: str = ""


def bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def make_result(payload: Any, reasoning: str, confidence: float, warnings: list[str] | None = None) -> AgentResult:
    return AgentResult(payload=payload, reasoning=reasoning, confidence=bounded_confidence(confidence), warnings=warnings)
