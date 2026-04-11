from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict


def send_email(*, to_name: str, subject: str, body: str) -> Dict[str, Any]:
    return {
        "success": True,
        "message_id": str(uuid4()),
        "provider_status": "sent_simulated",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "to_name": to_name,
        "subject": subject,
        "body_preview": body[:120],
    }
