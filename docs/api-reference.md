# API Reference

[Back to README](../README.md) · [Demo guide](demo-guide.md) · [Security and privacy](security-and-privacy.md)

FastAPI is created in [`api/app.py`](../api/app.py). Workflow transport routes use the `/api` prefix from [`api/router.py`](../api/router.py); `/health` and `/demo` are application-level routes. Interactive OpenAPI documentation is available at `/docs` while the application is running.

## Authentication

All POST workflow/action/demo mutation routes below require `Authorization: Bearer <token>` in the default protected mode. GET routes are read-only. See [security and privacy](security-and-privacy.md#api-mutation-protection) for configuration. Demo routes also require `MAWI_DEMO_MODE=true`.

## Application routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Return `{"status":"ok"}` |
| GET | `/demo` | Serve the local demo UI |

## Workflow and action routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/workflows/start?workflow=deal-followup` | Start a registered workflow for a `deal_id` |
| GET | `/api/actions?status=pending_approval` | List actions, optionally filtered by status |
| POST | `/api/actions/approve` | Approve and resume an action |
| POST | `/api/actions/edit` | Edit an action and return it to pending approval |
| POST | `/api/actions/reject` | Reject an action with a reason |
| GET | `/api/deals/{deal_id}` | Fetch the latest persisted deal context |
| GET | `/api/runs/summary?deal_id=...` | Fetch a run summary by `deal_id` or `run_id` |
| GET | `/api/prompts/diagnostics?limit=25` | Fetch prompt diagnostics and sampled traces |
| POST | `/api/workflows/intervention/run` | Run `deal_intervention_workflow` explicitly |
| POST | `/api/workflows/crm-sync/run` | Run `crm_sync_workflow` explicitly |
| GET | `/api/crm/sync-status?deal_id=...` | Fetch CRM sync status by `deal_id` or `run_id` |

The start route accepts aliases `deal-followup` and `crm-sync`, plus the exact IDs `deal_followup_workflow`, `new_deal_outreach_workflow`, `deal_intervention_workflow`, and `crm_sync_workflow`. CRM sync receives the explicit API trigger context required by its trigger contract.

### Core request examples

Start:

```json
{"deal_id": "deal_123"}
```

Approve:

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "reviewer@example.test",
  "reply_received": true,
  "meeting_booked": false
}
```

Edit:

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "reviewer@example.test",
  "preview": "Updated subject line",
  "body_draft": "Refined body copy"
}
```

Reject:

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "reviewer@example.test",
  "reason": "Tone needs revision"
}
```

The explicit intervention and CRM sync routes each accept `{"deal_id":"deal_123"}`.

## Demo routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/demo/scenarios` | List canonical fictional scenarios |
| POST | `/api/demo/scenarios/{scenario_id}/start` | Start one canonical scenario |
| POST | `/api/demo/reset` | Delete canonical demo records |
| GET | `/api/demo/runs/{run_id}/timeline` | Read persisted stage timeline |
| GET | `/api/demo/runs/{run_id}/audit` | Read persisted audit events |
| GET | `/api/demo/runs/{run_id}/telemetry` | Read persisted run telemetry |

## Error model

Handled lookup and validation failures use:

```json
{
  "error": "unknown_workflow",
  "message": "Unknown workflow name: invalid-workflow"
}
```

Known values include `unknown_workflow` (400), `invalid_request` (400), `action_not_found` (404), `deal_state_not_found` (404), `run_summary_not_found` (404), `demo_scenario_not_found` (404), and `demo_run_not_found` (404). Authentication failures use FastAPI `detail` responses with 401 or 503; disabled demo routes return 403.

## Compatibility and migration notes

- **2026-04-14 — mutation authentication:** mutation endpoints enforce bearer-token authentication by default. Callers must set `MAWI_API_BEARER_TOKEN` and send the authorization header, or explicitly enable both local-development bypass variables. This is a behavior change for previously unprotected hosted endpoints.
- **2026-04-11 — documentation policy:** implementation claims require trigger, orchestration, execution, evaluation, and persistence evidence; API signature changes require a migration note.

Add future notes only when method signatures, schemas, endpoint contracts, lifecycle status semantics, or persisted contracts materially change.
