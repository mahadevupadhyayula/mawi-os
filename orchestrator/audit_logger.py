"""
Purpose:
Orchestrator module `audit_logger` for coordinating workflow execution mechanics.

Technical Details:
Handles sequencing, retries, and auditability while delegating domain decisions to dedicated agents and tools.
"""

from __future__ import annotations

from datetime import datetime, timezone


def log_step(step: str, message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{step}] {message}")
