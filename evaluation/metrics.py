from __future__ import annotations


def compute_metrics(records: list[dict]) -> dict:
    if not records:
        return {"count": 0, "success_rate": 0.0}
    successes = sum(1 for r in records if r.get("success"))
    return {"count": len(records), "success_rate": successes / len(records)}
