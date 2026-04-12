from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import data.db_client as db_client_module
from data.db_client import DBClient


@pytest.fixture(scope="session")
def mawi_db_path() -> Path:
    """Test database location backed by the MAWI_DB_PATH environment variable."""
    path = Path(".mawi/test.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["MAWI_DB_PATH"] = str(path)
    db_client_module.DEFAULT_DB_PATH = path
    return path


@pytest.fixture(scope="function")
def reset_db(mawi_db_path: Path) -> Path:
    """Recreate the SQLite schema from scratch for deterministic test isolation."""
    if mawi_db_path.exists():
        mawi_db_path.unlink()
    DBClient(mawi_db_path)
    return mawi_db_path


@pytest.fixture
def sample_deal_payload() -> dict[str, Any]:
    return {
        "deal_id": "deal-test-001",
        "account": "Acme Corp",
        "contact_name": "Jordan Lee",
        "persona": "VP Sales",
        "deal_stage": "proposal",
        "days_since_reply": 7,
        "last_touch_summary": "Shared ROI model and waiting for response.",
        "known_objections": ["budget timing", "integration risk"],
        "last_updated": "2026-04-12T00:00:00+00:00",
    }


@pytest.fixture
def sample_personas() -> dict[str, dict[str, Any]]:
    return {
        "vp_sales": {"tone": "direct", "priority": "pipeline velocity"},
        "revops": {"tone": "analytical", "priority": "forecast confidence"},
        "cto": {"tone": "technical", "priority": "integration risk"},
    }


@pytest.fixture
def context_envelope_fixture(sample_deal_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": {
            "deal_id": sample_deal_payload["deal_id"],
            "workflow_stage": "initialized",
        },
        "raw_data": sample_deal_payload,
        "history": [],
    }


@pytest.fixture
def workflow_api(reset_db: Path, mawi_db_path: Path) -> Any:
    os.environ["MAWI_DB_PATH"] = str(mawi_db_path)
    db_client_module.DEFAULT_DB_PATH = mawi_db_path
    from api.service import WorkflowAPI
    from orchestrator.runner import WorkflowOrchestrator

    return WorkflowAPI(orchestrator=WorkflowOrchestrator())


@pytest.fixture
def api_client(workflow_api: Any) -> Any:
    fastapi = pytest.importorskip("fastapi")
    _ = fastapi  # appease linters
    from fastapi.testclient import TestClient

    from api.app import create_web_app
    from api.router import get_service

    app = create_web_app()
    app.dependency_overrides[get_service] = lambda: workflow_api
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def run_test_workflow(workflow_api: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Start a workflow and return the latest persisted/final deal state."""

    def _run(input_data: dict[str, Any]) -> dict[str, Any]:
        deal_id = str(input_data.get("deal_id", "deal-test-001"))
        workflow_name = input_data.get("workflow_name")

        state = workflow_api.start_workflow(deal_id, workflow_name=workflow_name)
        actions = workflow_api.get_actions(status="pending_approval")
        for action in actions:
            if action.get("deal_id") == deal_id and action.get("action_id"):
                workflow_api.approve_action(str(action["action_id"]), approver="pytest")

        return workflow_api.get_deal_state(deal_id) if actions else state

    return _run
