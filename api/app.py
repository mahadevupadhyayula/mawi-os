from __future__ import annotations

"""Minimal bootstrap module.

This project exposes API behavior through WorkflowAPI service methods in api/service.py.
A web framework adapter (FastAPI/Flask) can be layered on top without changing domain logic.
"""

from api.service import WorkflowAPI


def create_app_service() -> WorkflowAPI:
    return WorkflowAPI()
