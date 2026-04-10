from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentInput:
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    structured: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.0
