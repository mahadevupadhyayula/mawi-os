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
