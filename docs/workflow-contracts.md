# Workflow Contracts

[Back to README](../README.md) · [Architecture](architecture.md) · [API reference](api-reference.md)

## Definition of implemented

A workflow is **Implemented** only when all five elements exist:

1. **Trigger** — concrete event or signal detection.
2. **Orchestration** — ordered stages run through the orchestrator.
3. **Execution** — at least one action/tool path is runnable.
4. **Evaluation** — outcomes are analyzed after execution.
5. **Persistence** — state and outcomes are stored for resume and audit.

A workflow missing any element is partial and must not be presented as implemented.

## Implemented workflow evidence

The registry exposes exactly these four built-in workflow IDs:

| Workflow ID | Ordered stages | Evidence |
| --- | --- | --- |
| `deal_followup_workflow` | signal, context, strategist, action, execution, evaluator | [definition](../workflows/deal_followup_workflow.py), [trigger](../workflows/triggers.py) |
| `new_deal_outreach_workflow` | signal, context, strategist, action, execution, evaluator | [definition](../workflows/new_deal_outreach_workflow.py), [trigger](../workflows/triggers.py) |
| `deal_intervention_workflow` | signal, context, intervention, strategist, action, execution, evaluator | [definition](../workflows/deal_intervention_workflow.py), [trigger](../workflows/triggers.py) |
| `crm_sync_workflow` | signal, context, CRM, execution, evaluator | [definition](../workflows/crm_sync_workflow.py), [trigger](../workflows/triggers.py) |

All four use the shared [registry](../workflows/registry.py), [runner](../orchestrator/runner.py), execution/evaluation agents, and repository-backed persistence. Deal intervention adds the [intervention log repository](../data/repositories/intervention_log_repo.py); CRM sync adds the [CRM sync log repository](../data/repositories/crm_sync_log_repo.py). Planned or dynamically registered metadata is not evidence that another workflow meets the implementation definition.

## Structured context envelope

The envelope evolves through explicit stage updates rather than ad hoc payload replacement. Its typed sections are:

- `meta`
- `signal_context`
- `deal_context`
- `decision_context`
- `action_context`
- `execution_context`
- `outcome_context`

The authoritative models are in [`context/models.py`](../context/models.py), and envelope serialization/update behavior is in [`context/envelope.py`](../context/envelope.py).

## Shared prompt input contract

Agent prompt rendering uses these stable fields:

| Field | Requirement |
| --- | --- |
| `workflow_id` | Defaults to `deal_followup_workflow` when omitted |
| `workflow_goal` | Required |
| `stage_name` | Required |
| `policy_mode` | Required |
| `expected_output_schema` | Required |

Missing required fields fail prompt rendering before model execution. Representative stage output contracts are:

- `signal_agent`: `SignalContext(stalled, days_since_reply, urgency, trigger_reason, reasoning, confidence)`
- `context_agent`: `DealContext(persona, deal_stage, known_objections, recent_timeline, recommended_tone, reasoning, confidence)`
- `strategist_agent`: `DecisionContext(strategy_id, strategy_type, message_goal, fallback_strategy, memory_evidence_used, memory_confidence_impact, memory_rationale, reasoning, confidence)`
- `action_agent`: `ActionPlanContext(plan_id, steps[], status, reasoning, confidence)`
- `execution_agent`: `ExecutionContext(execution_id, status, email_result, crm_result, tool_events, reasoning, confidence)`
- `evaluator_agent`: `OutcomeContext(outcome_label, insight, recommended_adjustment, reasoning, confidence)`

Prompt templates and validation live in [`agents/prompt_templates.py`](../agents/prompt_templates.py), [`agents/contracts.py`](../agents/contracts.py), and [`agents/prompts/`](../agents/prompts/).

## Approval and execution contract

Actions can be approved, edited, or rejected. Policy decisions and lifecycle changes are persisted, while execution proceeds only through the existing execution agent and simulated adapters. Optional LLM generation changes candidate content, not the approval boundary, stage sequence, workflow ID, or execution tool interface.

## Update policy

When a workflow first meets all five criteria, documentation should add its exact workflow ID and direct evidence for trigger, orchestration, execution, evaluation, and persistence. API signature or schema changes also require an API migration note.
