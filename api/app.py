"""
Purpose:
API module `app` that exposes workflow operations to callers.

Technical Details:
Provides service-facing interfaces for human-in-the-loop actions while keeping transport concerns decoupled from domain logic.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.router import router
from api.service import WorkflowAPI


def create_app_service() -> WorkflowAPI:
    return WorkflowAPI()


def create_web_app() -> FastAPI:
    app = FastAPI(title="MAWI Workflow API")
    app.include_router(router)
    static_directory = Path(__file__).with_name("static")
    app.mount("/demo/static", StaticFiles(directory=static_directory), name="demo-static")

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/demo", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(static_directory / "demo.html", media_type="text/html")

    return app
