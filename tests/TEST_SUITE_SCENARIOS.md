# Test Suite Coverage — Cases and Scenarios

This document records the test cases and scenarios currently covered by the MAWI test suite.

## Workflow-Level Coverage

### Deal Follow-up Workflow (`deal_followup_workflow`)
- Trigger threshold behavior (`days_since_reply >= 5`).
- Step order and gated progression through approval.
- Full execution + evaluation after approval resume.

Source: `tests/workflows/test_deal_followup_workflow.py`.

### New Deal Outreach Workflow (`new_deal_outreach_workflow`)
- Trigger behavior for day-0/no-prior-outbound conditions.
- Step order and gated progression through approval.
- Full execution + evaluation after approval resume.

Source: `tests/workflows/test_new_deal_outreach_workflow.py`.

## End-to-End Scenario Coverage

Scenario tests in `tests/scenarios/test_sales_workflow_scenarios.py` currently cover:

- No-reply follow-up trigger path.
- New-deal outreach trigger path.
- No-trigger path when follow-up threshold is not met.
- Low-confidence routing to `pending_approval`.
- Rejected action plan halting execution.
- Policy-violating generated content blocked with escalation metadata.
- Successful execution capturing tool events and outcome labels.

## Integration Coverage

- API workflow lifecycle endpoints and interactions.
- Action lifecycle service behavior for start/approve/reject flows.

Sources:
- `tests/integration/test_api_endpoints.py`
- `tests/integration/test_action_lifecycle_service.py`

## Unit Coverage Areas

Current unit tests include:

- Agent behavior: signal, context, strategist, action, execution, evaluator.
- Approval policy and controls.
- Tool adapters (email/SMS/CRM/deal).
- Prompt contracts, diagnostics, rollout and simulation checks.
- Retry and summary behavior.
- Memory adaptation behavior.
- Workflow persistence repository behavior.

Representative sources:
- `tests/unit/*.py`
- `tests/test_policy_controls.py`
- `tests/test_prompt_contracts.py`
- `tests/test_prompt_diagnostics.py`
- `tests/test_prompt_experiment_rollout.py`
- `tests/test_prompt_simulation_regression.py`
- `tests/test_retry_and_summary.py`
- `tests/test_memory_adaptation.py`
- `tests/persistence/test_workflow_persistence.py`

## Fixtures and Snapshot Assets

- Prompt rendering scenarios and expected output samples.
- Workflow trigger scenarios fixtures.
- Prompt snapshots used for regression checks.

Sources:
- `tests/fixtures/prompt_render_scenarios.json`
- `tests/fixtures/prompt_output_samples.json`
- `tests/fixtures/workflow_trigger_scenarios.json`
- `tests/snapshots/prompts/*.txt`

## Maintenance Notes

When adding or removing tests, update this file in the same change so this inventory remains accurate.
