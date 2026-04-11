from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def fetch_deal_data(deal_id: str) -> Dict[str, Any]:
    # Simulated retrieval
    now = datetime.now(timezone.utc)
    return {
        "deal_id": deal_id,
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 6,
        "last_touch_summary": "Sent ROI model and case study.",
        "known_objections": ["budget timing", "integration risk"],
        "last_updated": now.isoformat(),
    }
