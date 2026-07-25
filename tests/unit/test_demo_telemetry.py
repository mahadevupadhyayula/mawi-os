from __future__ import annotations

from datetime import datetime, timezone

from demo.api import DemoAPI
from api.service import WorkflowAPI
from orchestrator.runner import WorkflowOrchestrator


def _started_demo(reset_db) -> tuple[DemoAPI, str]:
    api = DemoAPI(WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=0.99)))
    started = api.start_scenario("stalled-deal-approval")
    return api, started["run_id"]


def test_deterministic_telemetry_preserves_missing_optional_fields(reset_db) -> None:
    api, run_id = _started_demo(reset_db)

    telemetry = api.telemetry(run_id)

    assert telemetry["llm_enabled"] is False
    assert telemetry["providers"] == []
    assert telemetry["models"] == []
    assert telemetry["fallback_reasons"] == []
    assert telemetry["approval_state"] == "pending_approval"
    assert telemetry["execution_status"] == "not_started"
    assert telemetry["outcome_label"] is None
    assert telemetry["stage_runs"]


def test_mocked_llm_fallback_and_retry_evidence_is_aggregated(reset_db) -> None:
    api, run_id = _started_demo(reset_db)
    with api.db.tx() as conn:
        conn.execute(
            """
            INSERT INTO prompt_runs (
                run_id, workflow_id, agent_id, prompt_name, prompt_profile_id,
                prompt_profile_version, prompt_schema_version, latency_ms, status,
                error_type, fallback_used, llm_enabled, provider, model,
                fallback_reason, created_at
            ) VALUES (?, 'deal_followup_workflow', 'signal_agent', 'signal_prompt.txt',
                'test', 'test', 'v1', 12, 'fallback', 'invalid_json', 1, 1,
                'simulated', 'mock-model', 'llm_error:invalid_json', ?)
            """,
            (run_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "UPDATE action_steps SET retry_count=2 WHERE run_id=? AND step_order=1",
            (run_id,),
        )

    telemetry = api.telemetry(run_id)

    assert telemetry["llm_enabled"] is True
    assert telemetry["providers"] == ["simulated"]
    assert telemetry["models"] == ["mock-model"]
    assert telemetry["fallback_detected"] is True
    assert telemetry["fallback_reasons"] == ["llm_error:invalid_json"]
    assert telemetry["error_classes"] == ["invalid_json"]
    assert telemetry["retry_count"] == 2
