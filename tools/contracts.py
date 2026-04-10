from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def receipt(ok: bool, tool: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": ok,
        "tool": tool,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
