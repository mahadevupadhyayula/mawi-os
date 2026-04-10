from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InMemoryRepository:
    items: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.items.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.items[key] = value

    def all(self) -> Dict[str, Any]:
        return self.items


@dataclass
class ListRepository:
    items: List[Any] = field(default_factory=list)

    def append(self, value: Any) -> None:
        self.items.append(value)

    def all(self) -> List[Any]:
        return list(self.items)
