# Current Workflow Status

This file tracks workflow implementation status based on the repository's implementation criteria:
**trigger + orchestration + execution + evaluation + persistence**.

## Workflow Status Matrix

| Workflow | Status | Notes |
|---|---|---|
| `deal_followup_workflow` | Implemented | End-to-end trigger, orchestration, execution, evaluation, and persistence are in place. |
| `new_deal_outreach_workflow` | Implemented | Triggered for day-0 deals with no prior outbound activity; uses the same end-to-end orchestration/evaluation/persistence path as follow-up. |
| `deal_risk_detection_workflow` | Not implemented | Planned in roadmap only. |
| `deal_intervention_workflow` | Implemented | Triggered by stalled/no-reply/high-risk signals; registered and runnable via API + orchestration path. |
| `crm_sync_workflow` | Implemented | Triggered by explicit API request or post-action CRM sync events; uses `crm_agent` execution path and sync-status logging. |
| `multi_threading_workflow` | Not implemented | Planned in roadmap only (not registered). |
| `meeting_followup_workflow` | Not implemented | Planned in roadmap only. |
| `objection_handling_workflow` | Not implemented | Planned in roadmap only. |
| `multi_channel_outreach_workflow` | Not implemented | Planned in roadmap only. |
| `adaptive_sequencing_workflow` | Not implemented | Planned in roadmap only. |
| `revenue_forecasting_workflow` | Not implemented | Planned in roadmap only. |
| `rep_performance_optimization_workflow` | Not implemented | Planned in roadmap only. |
| `workflow_builder` | Not implemented | Planned in roadmap only. |

## Current Runtime Behavior

- **Registered workflows:** `crm_sync_workflow`, `deal_followup_workflow`, `deal_intervention_workflow`, `new_deal_outreach_workflow`.
- **Trigger behavior:**
  - `deal_followup_workflow`: runs when `should_trigger_deal_followup` passes (`days_since_reply >= 5`).
  - `new_deal_outreach_workflow`: runs when `should_trigger_new_deal_outreach` passes (`days_since_reply == 0` and no prior outbound markers).
  - `deal_intervention_workflow`: runs on `deal_stalled`/`no_reply`, explicit `risk_tier` high/critical, or inferred high-risk score thresholds.
  - `crm_sync_workflow`: runs for explicit API CRM sync requests or post-action execution events with execution references/sync-required payloads.
- **Approval behavior:** action plans are auto-approved if confidence meets threshold; otherwise they are queued for human approval (`waiting_approval`) before execution.

## Demo Runtime Modes (Safety Notes)

- **Mode A — deterministic (safe/offline):** set `MAWI_LLM_ENABLED=false` (default). No external API key is required, and workflow behavior remains fully auditable.
- **Mode B — live LLM:** set `MAWI_LLM_ENABLED=true` and provide `OPENAI_API_KEY` to enable provider-backed JSON generation for agent stages.
- **Fallback guarantee:** on provider timeout, invalid JSON, missing required fields, or missing key/provider errors, agent stages fall back to deterministic payloads so orchestration contracts and approval gating stay intact.
- **Invariant controls:** orchestration sequencing, policy/approval checks, and execution tool boundaries are unchanged between modes.
