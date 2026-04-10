from __future__ import annotations

from collections import defaultdict
from typing import Dict, List


class InsightIndex:
    def __init__(self) -> None:
        self.by_persona: Dict[str, List[str]] = defaultdict(list)

    def add(self, persona: str, insight: str) -> None:
        self.by_persona[persona].append(insight)

    def get(self, persona: str) -> List[str]:
        return self.by_persona.get(persona, [])
