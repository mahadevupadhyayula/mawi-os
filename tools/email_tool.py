from __future__ import annotations

from uuid import uuid4

from tools.contracts import receipt
from tools.simulator import simulate_success


def send_email(subject: str, body: str, to: str) -> dict:
    ok = simulate_success(0.98)
    payload = {
        "message_id": str(uuid4()),
        "to": to,
        "subject": subject,
        "body_preview": body[:120],
        "delivery_status": "sent" if ok else "failed",
    }
    return receipt(ok, "send_email", payload)
