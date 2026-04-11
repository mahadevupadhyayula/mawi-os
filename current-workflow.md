# current workflow

- **workflow names:** `deal_followup_workflow`
- **trigger behavior:** Runs only when `should_trigger_deal_followup` passes; otherwise skipped.
- **approval behavior:** Action is auto-approved if confidence meets threshold, otherwise queued for human approval (`waiting_approval`) before execution.
