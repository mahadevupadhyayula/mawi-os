from __future__ import annotations

from tools.contracts import receipt
from tools.simulator import simulate_success


def update_crm(deal_id: str, patch: dict) -> dict:
    ok = simulate_success(0.97)
    payload = {"deal_id": deal_id, "patch": patch, "status": "updated" if ok else "failed"}
    return receipt(ok, "update_crm", payload)
