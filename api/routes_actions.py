from __future__ import annotations

from api.dependencies import engine


def get_actions() -> dict:
    return {"items": engine.approval_queue.all()}
