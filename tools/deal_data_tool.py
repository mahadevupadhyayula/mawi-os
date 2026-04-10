from __future__ import annotations

from tools.contracts import receipt


def fetch_deal_data(deal_id: str) -> dict:
    data = {
        "deal_id": deal_id,
        "no_reply_days": 6,
        "contact_email": "buyer@example.com",
        "account_profile": "mid-market saas",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "open_objections": ["unclear ROI"],
        "interaction_summary": "2 demos, 1 proposal",
    }
    return receipt(True, "fetch_deal_data", data)
