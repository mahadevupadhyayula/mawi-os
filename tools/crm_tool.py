"""
Purpose:
Tool integration module `crm_tool` for external side effects used by workflows.

Technical Details:
Wraps provider behavior behind stable interfaces and returns structured execution metadata for deterministic state updates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def update_crm(*, deal_id: str, note: str, message_id: str) -> Dict[str, Any]:
    return {
        "success": True,
        "deal_id": deal_id,
        "record_id": f"crm-{deal_id}",
        "status": "updated_simulated",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "linked_message_id": message_id,
    }
