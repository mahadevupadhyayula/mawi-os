from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from api.app import create_web_app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(create_web_app()) as test_client:
        yield test_client


def test_demo_page_and_static_assets_load(client) -> None:
    page = client.get("/demo")
    stylesheet = client.get("/demo/static/demo.css")
    script = client.get("/demo/static/demo.js")

    assert page.status_code == stylesheet.status_code == script.status_code == 200
    assert "MAWI Workflow Operator" in page.text
    assert "Portfolio demo" in page.text
    assert "simulated" in page.text.lower()
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert "javascript" in script.headers["content-type"]


def test_demo_script_references_existing_demo_and_approval_routes() -> None:
    script = (Path(__file__).parents[2] / "api" / "static" / "demo.js").read_text(encoding="utf-8")
    routes = {
        "/api/demo/scenarios",
        "/api/demo/reset",
        "/api/demo/runs/",
        "/api/actions/approve",
        "/api/actions/edit",
        "/api/actions/reject",
    }

    for route in routes:
        assert route in script
