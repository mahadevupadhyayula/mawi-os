"""
Purpose:
Tool integration module `sms_tool` for external side effects used by workflows.

Technical Details:
Wraps SMS provider behavior behind stable interfaces and returns structured execution metadata for deterministic state updates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


def send_sms(*, to_name: str, body: str) -> Dict[str, Any]:
    return {
        "success": True,
        "sms_id": str(uuid4()),
        "provider_status": "queued_simulated",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "to_name": to_name,
        "body_preview": body[:120],
        "channel_metadata": {
            "carrier": "simulated",
            "segments": max(1, (len(body) + 159) // 160),
            "delivery_window": "immediate",
        },
    }
