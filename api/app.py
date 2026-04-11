"""
Purpose:
API module `app` that exposes workflow operations to callers.

Technical Details:
Provides service-facing interfaces for human-in-the-loop actions while keeping transport concerns decoupled from domain logic.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.router import router
from api.service import WorkflowAPI


def create_app_service() -> WorkflowAPI:
    return WorkflowAPI()


def create_web_app() -> FastAPI:
    app = FastAPI(title="MAWI Workflow API")
    app.include_router(router)
    return app
