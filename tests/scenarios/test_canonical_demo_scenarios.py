from __future__ import annotations

from agents import prompt_templates
from agents.llm_client import LLMResult
from api.service import WorkflowAPI
from demo.scenarios import SCENARIO_NAMES, load_scenario, load_scenarios
from orchestrator.runner import WorkflowOrchestrator


def _start(scenario: dict, *, approval_threshold: float = 0.99) -> tuple[WorkflowAPI, dict]:
    api = WorkflowAPI(orchestrator=WorkflowOrchestrator(approval_threshold=approval_threshold))
    state = api.start_workflow(
        scenario["deal"]["deal_id"],
        workflow_name=scenario["workflow_id"],
        trigger_context=scenario["deal"],
    )
    return api, state


def _action_for(api: WorkflowAPI, deal_id: str) -> dict:
    return next(action for action in api.get_actions("pending_approval") if action["deal_id"] == deal_id)


def test_all_canonical_fixtures_load_with_required_inputs() -> None:
    scenarios = load_scenarios()

    assert tuple(item["scenario_id"] for item in scenarios) == SCENARIO_NAMES
    for scenario in scenarios:
        assert scenario["workflow_id"] == "deal_followup_workflow"
        assert scenario["deal"]["deal_id"].startswith("demo-")
        assert scenario["deal"]["days_since_reply"] >= 5
        assert scenario["deal"]["known_objections"]
        assert scenario["approval"]["decision"] in {"approve", "reject"}


def test_stalled_deal_waits_for_approval_then_resumes_and_persists(reset_db) -> None:
    scenario = load_scenario("stalled-deal-approval")
    api, started = _start(scenario)

    assert started["meta"]["workflow_stage"] == scenario["expected"]["initial_stage"]
    assert started["signal_context"] and started["deal_context"] and started["decision_context"]
    assert started["action_context"]["confidence"] < api.orchestrator.approval_threshold
    assert started["action_plan"]["status"] == "pending_approval"

    action = _action_for(api, scenario["deal"]["deal_id"])
    approval = scenario["approval"]
    api.approve_action(
        action["action_id"],
        approval["actor"],
        reply_received=approval["reply_received"],
        meeting_booked=approval["meeting_booked"],
    )

    final = api.get_deal_state(scenario["deal"]["deal_id"])
    assert final["meta"]["workflow_stage"] == scenario["expected"]["final_stage"]
    assert final["execution_context"]["status"] == "executed"
    assert final["outcome_context"] is not None
    assert api.orchestrator.workflow_repo.get_latest_envelope(scenario["deal"]["deal_id"]) == final


def test_rejected_action_records_reason_without_executing_tools(reset_db, monkeypatch) -> None:
    scenario = load_scenario("rejected-action")
    api, started = _start(scenario)
    tool_calls: list[str] = []
    monkeypatch.setattr("agents.execution_agent.send_email", lambda **_kwargs: tool_calls.append("email"))
    monkeypatch.setattr("agents.execution_agent.update_crm", lambda **_kwargs: tool_calls.append("crm"))

    assert started["meta"]["workflow_stage"] == "waiting_approval"
    action = _action_for(api, scenario["deal"]["deal_id"])
    rejection = api.reject_action(
        action["action_id"], scenario["approval"]["actor"], scenario["approval"]["reason"]
    )

    persisted = api.orchestrator.action_repo.get_action(action["action_id"])
    state = api.get_deal_state(scenario["deal"]["deal_id"])
    assert rejection["reason"] == scenario["approval"]["reason"]
    assert persisted["status"] == "rejected"
    assert persisted["rejection_reason"] == scenario["approval"]["reason"]
    assert state["action_context"]["status"] == "rejected"
    assert state["execution_context"] is None
    assert state["outcome_context"] is None
    assert tool_calls == []


def test_llm_failure_uses_deterministic_signal_and_preserves_contract(reset_db, monkeypatch) -> None:
    scenario = load_scenario("llm-fallback")
    simulation = scenario["llm_simulation"]
    calls = 0

    def invalid_json_without_network(request):
        nonlocal calls
        calls += 1
        error = simulation["failure_type"] if calls == 1 else "provider_error"
        return LLMResult(
            raw_text=simulation["raw_response"], payload=None, latency_ms=0,
            provider="simulated", model=request.model, error=error, token_usage=None,
        )

    monkeypatch.setenv("MAWI_LLM_ENABLED", "true")
    monkeypatch.setattr("agents.llm_client.generate_json", invalid_json_without_network)
    api, started = _start(scenario)

    expected_signal = scenario["expected"]["deterministic_signal"]
    assert {key: started["signal_context"][key] for key in expected_signal} == expected_signal
    assert started["meta"]["workflow_stage"] == "waiting_approval"
    assert started["deal_context"] and started["decision_context"] and started["action_context"]
    run_id = api.orchestrator.workflow_repo.get_latest_run_id(scenario["deal"]["deal_id"])
    with prompt_templates._PROMPT_DIAGNOSTICS_REPO.db.tx() as conn:
        signal_run = dict(
            conn.execute(
                "SELECT llm_enabled, fallback_reason FROM prompt_runs WHERE run_id=? AND agent_id='signal_agent'",
                (run_id,),
            ).fetchone()
        )
    assert signal_run["llm_enabled"] == 1
    assert signal_run["fallback_reason"] == scenario["expected"]["fallback_reason"]
    assert calls >= 1
