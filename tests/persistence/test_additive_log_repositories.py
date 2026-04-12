from __future__ import annotations

import json

from data.repositories.crm_sync_log_repo import CRMSyncLogRepository
from data.repositories.intervention_log_repo import InterventionLogRepository
from data.repositories.workflow_repo import WorkflowRepository
from data.repositories.workflow_state_repo import WorkflowStateRepository


def _seed_run(repo: WorkflowRepository, deal_id: str = "deal-log-repos") -> str:
    repo.create_or_update_deal(
        deal_id,
        {
            "account": "Acme Corp",
            "contact_name": "Taylor",
            "persona": "VP Sales",
            "deal_stage": "proposal",
            "last_updated": "2026-04-12T00:00:00+00:00",
        },
    )
    return repo.create_run(deal_id, workflow_name="deal_followup", stage="initialized", status="running")


def test_intervention_log_repository_insert_query_update(reset_db) -> None:
    _ = reset_db
    workflow_repo = WorkflowRepository()
    run_id = _seed_run(workflow_repo)

    repo = InterventionLogRepository(db=workflow_repo.db)
    log_id = repo.insert_log(
        run_id=run_id,
        deal_id="deal-log-repos",
        intervention_type="manual_review",
        status="pending",
        details={"reason": "tone_check"},
    )

    rows = repo.list_logs(run_id=run_id)
    assert len(rows) == 1
    assert rows[0]["id"] == log_id
    assert rows[0]["deal_id"] == "deal-log-repos"
    assert json.loads(rows[0]["details_json"])["reason"] == "tone_check"

    repo.update_log(log_id, status="completed", details={"reason": "tone_check", "approved": True})
    updated = repo.list_logs(run_id=run_id)[0]
    assert updated["status"] == "completed"
    assert json.loads(updated["details_json"])["approved"] is True


def test_crm_sync_log_repository_insert_query_update(reset_db) -> None:
    _ = reset_db
    workflow_repo = WorkflowRepository()
    run_id = _seed_run(workflow_repo, deal_id="deal-crm-sync")

    repo = CRMSyncLogRepository(db=workflow_repo.db)
    log_id = repo.insert_log(
        run_id=run_id,
        deal_id="deal-crm-sync",
        sync_status="queued",
        request={"fields": ["deal_stage"]},
    )

    rows = repo.list_logs(deal_id="deal-crm-sync")
    assert len(rows) == 1
    assert rows[0]["id"] == log_id
    assert rows[0]["sync_status"] == "queued"

    repo.update_log(
        log_id,
        sync_status="success",
        response={"crm_id": "abc-123"},
        synced_at="2026-04-12T01:00:00+00:00",
    )
    updated = repo.list_logs(run_id=run_id)[0]
    assert updated["sync_status"] == "success"
    assert json.loads(updated["response_json"])["crm_id"] == "abc-123"


def test_workflow_state_repository_upsert_query_update(reset_db) -> None:
    _ = reset_db
    workflow_repo = WorkflowRepository()
    run_id = _seed_run(workflow_repo, deal_id="deal-workflow-state")

    repo = WorkflowStateRepository(db=workflow_repo.db)
    repo.upsert_state(
        run_id=run_id,
        deal_id="deal-workflow-state",
        workflow_name="deal_followup",
        stage="planning",
        status="running",
        state={"attempt": 1},
    )

    state = repo.get_state(run_id=run_id)
    assert state is not None
    assert state["stage"] == "planning"
    assert json.loads(state["state_json"])["attempt"] == 1

    repo.update_state(
        run_id=run_id,
        deal_id="deal-workflow-state",
        stage="completed",
        status="completed",
        state={"attempt": 2, "result": "ok"},
    )
    updated = repo.get_state(deal_id="deal-workflow-state")
    assert updated is not None
    assert updated["status"] == "completed"
    assert json.loads(updated["state_json"])["result"] == "ok"
