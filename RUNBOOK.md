# Runbook / Test Planning

## Scenario matrix
1. Auto-approved action (confidence >= threshold) -> executes and evaluates.
2. Manual approval required (confidence < threshold) -> pending approval.
3. Rejection path -> action rejected, no execution.
4. Retry path -> transient tool failure handled by retry policy.
5. Tool failure beyond retries -> dead-letter entry.
6. Delayed outcome -> evaluator runs with pending/default outcome.

## Production readiness checklist
- Structured logs with stage/deal/run identifiers.
- Approval API access control (authn/authz) to be wired at gateway.
- Data retention policy for action/outcome history.
- Prompt and agent version tracking in context sections.
- Metrics export (success rate, approval latency, execution failures).
