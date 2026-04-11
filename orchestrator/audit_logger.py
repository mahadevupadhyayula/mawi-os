"""
Purpose:
Orchestrator module `audit_logger` for coordinating workflow execution mechanics.

Technical Details:
Handles sequencing, retries, and auditability while delegating domain decisions to dedicated agents and tools.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def log_step(step: str, message: str, **fields: object) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    if fields:
        print(f"[{ts}] [{step}] {message} | {json.dumps(fields, sort_keys=True, default=str)}")
        return
    print(f"[{ts}] [{step}] {message}")
