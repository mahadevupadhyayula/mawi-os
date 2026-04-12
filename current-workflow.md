# Current Workflow Status

This file tracks workflow implementation status based on the repository's implementation criteria:
**trigger + orchestration + execution + evaluation + persistence**.

## Workflow Status Matrix

| Workflow | Status | Notes |
|---|---|---|
| `deal_followup_workflow` | Implemented | End-to-end trigger, orchestration, execution, evaluation, and persistence are in place. |
| `new_deal_outreach_workflow` | Implemented | Triggered for day-0 deals with no prior outbound activity; uses the same end-to-end orchestration/evaluation/persistence path as follow-up. |
| `deal_risk_detection_workflow` | Not implemented | Planned in roadmap only. |
| `deal_intervention_workflow` | Not implemented | Planned in roadmap only. |
| `multi_threading_workflow` | Not implemented | Planned in roadmap only. |
| `meeting_followup_workflow` | Not implemented | Planned in roadmap only. |
| `objection_handling_workflow` | Not implemented | Planned in roadmap only. |
| `multi_channel_outreach_workflow` | Not implemented | Planned in roadmap only. |
| `adaptive_sequencing_workflow` | Not implemented | Planned in roadmap only. |
| `revenue_forecasting_workflow` | Not implemented | Planned in roadmap only. |
| `rep_performance_optimization_workflow` | Not implemented | Planned in roadmap only. |
| `workflow_builder` | Not implemented | Planned in roadmap only. |

## Current Runtime Behavior

- **Registered workflows:** `deal_followup_workflow`, `new_deal_outreach_workflow`.
- **Trigger behavior:**
  - `deal_followup_workflow`: runs when `should_trigger_deal_followup` passes (`days_since_reply >= 5`).
  - `new_deal_outreach_workflow`: runs when `should_trigger_new_deal_outreach` passes (`days_since_reply == 0` and no prior outbound markers).
- **Approval behavior:** action plans are auto-approved if confidence meets threshold; otherwise they are queued for human approval (`waiting_approval`) before execution.
