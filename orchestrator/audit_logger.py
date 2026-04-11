from __future__ import annotations

from datetime import datetime, timezone


def log_step(step: str, message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{step}] {message}")
