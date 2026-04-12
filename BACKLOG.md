# MAWI — Backlog & Future Development

## 🧠 Overview

This document tracks workflows and capabilities outside the strict MVP boundary.

Status tags used in this document:

- **[Implemented]** — meets definition below end-to-end in code.
- **[Partial]** — some components exist, but not full end-to-end criteria.
- **[Not Implemented]** — planned only.
- Status tags must only be promoted based on verified code evidence for all required criteria (no roadmap-only promotion).

### Definition of Implemented

A workflow is **Implemented** when all five criteria exist in code:
**trigger + orchestration + execution + evaluation + persistence**.

Evidence references for implemented workflows (promotion requires all five criteria):

- **`deal_followup_workflow` [Implemented]**
  - Trigger/registry: [`workflows/triggers.py`](./workflows/triggers.py), [`workflows/registry.py`](./workflows/registry.py)
  - Orchestration: [`orchestrator/runner.py`](./orchestrator/runner.py)
  - Execution: [`agents/execution_agent.py`](./agents/execution_agent.py), [`tools/email_tool.py`](./tools/email_tool.py), [`tools/crm_tool.py`](./tools/crm_tool.py)
  - Evaluation: [`agents/evaluator_agent.py`](./agents/evaluator_agent.py), [`evaluation/outcome_analyzer.py`](./evaluation/outcome_analyzer.py)
  - Persistence: [`data/repositories/workflow_repo.py`](./data/repositories/workflow_repo.py), [`data/repositories/action_repo.py`](./data/repositories/action_repo.py), [`data/repositories/outcome_repo.py`](./data/repositories/outcome_repo.py)

- **`new_deal_outreach_workflow` [Implemented]**
  - Trigger/registry/workflow: [`workflows/triggers.py`](./workflows/triggers.py), [`workflows/registry.py`](./workflows/registry.py), [`workflows/new_deal_outreach_workflow.py`](./workflows/new_deal_outreach_workflow.py)
  - Orchestration/execution/evaluation/persistence: shared core path via runner, execution agent, evaluator, and repositories above.

- **`deal_intervention_workflow` [Implemented]**
  - Trigger/workflow/registry: [`workflows/triggers.py`](./workflows/triggers.py), [`workflows/deal_intervention_workflow.py`](./workflows/deal_intervention_workflow.py), [`workflows/registry.py`](./workflows/registry.py)
  - Orchestration/execution/evaluation/persistence: [`orchestrator/runner.py`](./orchestrator/runner.py), [`agents/execution_agent.py`](./agents/execution_agent.py), [`agents/evaluator_agent.py`](./agents/evaluator_agent.py), [`data/repositories/workflow_repo.py`](./data/repositories/workflow_repo.py)
  - API evidence: [`api/service.py`](./api/service.py), [`api/router.py`](./api/router.py), [`data/repositories/intervention_log_repo.py`](./data/repositories/intervention_log_repo.py)

- **`crm_sync_workflow` [Implemented]**
  - Trigger/workflow/registry: [`workflows/triggers.py`](./workflows/triggers.py), [`workflows/crm_sync_workflow.py`](./workflows/crm_sync_workflow.py), [`workflows/registry.py`](./workflows/registry.py)
  - Orchestration/execution/evaluation/persistence: [`orchestrator/runner.py`](./orchestrator/runner.py), [`agents/crm_agent.py`](./agents/crm_agent.py), [`agents/execution_agent.py`](./agents/execution_agent.py), [`agents/evaluator_agent.py`](./agents/evaluator_agent.py), [`data/repositories/workflow_repo.py`](./data/repositories/workflow_repo.py)
  - API evidence: [`api/service.py`](./api/service.py), [`api/router.py`](./api/router.py), [`data/repositories/crm_sync_log_repo.py`](./data/repositories/crm_sync_log_repo.py)

Status maintenance rule:

- Only mark any workflow/capability as **[Implemented]** once **all five** are present in code:
  **trigger + orchestration + execution + evaluation + persistence**.
- Otherwise use **[Partial]** or **[Not Implemented]**.

Roadmap organization:

- **Phase 1:** MVP execution wedge (current)
- **Phase 2:** intelligence expansion
- **Phase 3:** autonomous execution platform

---

## 🚀 Phase 1 (Current MVP)

### Included

- Deal follow-up workflow for stalled opportunities **[Implemented]**
- New deal outreach workflow for day-0 opportunities **[Implemented]**
- Signal → strategy → action pipeline **[Implemented]**
- Approval queue and policy-based human gate **[Implemented]**
- Tool execution stubs (email/CRM) **[Implemented]**
- Basic evaluation + memory feedback **[Partial]**

### MVP Exit Criteria

- Repeatable workflow runs end-to-end
- Approve/reject lifecycle is stable
- Action and outcome states are auditable
- Context handoff remains typed and debuggable

---

## 🟡 Phase 2 — Deal Intelligence System

### New Workflows

- New Deal Outreach Workflow **[Implemented]**
- Deal Risk Detection Workflow **[Not Implemented]**
- Deal Intervention Workflow **[Implemented]**
- Multi-threading Workflow **[Not Implemented]**
- Meeting Follow-up Workflow **[Not Implemented]**
- Objection Handling Workflow **[Not Implemented]**
- CRM Sync Workflow **[Implemented]**
- Multi-channel Outreach Workflow **[Not Implemented]**
- Adaptive Sequencing Workflow **[Not Implemented]**

### Capabilities

- Strategy agent with expanded playbook coverage
- Persona learning and message adaptation loops
- Rich memory retrieval and relevance ranking
- Operational insights dashboard for managers
- Better confidence calibration and policy controls

### Technical Milestones

- Move from rule-heavy logic to hybrid learned policies
- Expand event model and workflow trigger coverage
- Introduce workflow-level telemetry and alerting

---

## 🔴 Phase 3 — Autonomous Workflow Engine

### New Workflows

- Revenue Forecasting Workflow **[Not Implemented]**
- Rep Performance Optimization Workflow **[Not Implemented]**
- Workflow Builder (custom workflows) **[Not Implemented]**
- Cross-deal intelligence workflows **[Not Implemented]**

### Capabilities

- Guardrailed auto-execution mode
- Dynamic orchestration and branching control
- Continuous learning loop from outcome data
- Advanced context engine with long-horizon memory

### Platform Milestones

- Policy sandboxing and risk-tier execution modes
- Multi-tenant governance and access controls
- Versioned workflow definitions and rollback support

---

## 🔥 Long-Term Vision

MAWI evolves into an AI-native execution layer where:

- workflows are defined declaratively
- agents execute most operational steps autonomously
- humans supervise policy, quality, and strategic exceptions

---

## 🧠 Strategic Direction

1. **Assistive AI** — suggest actions
2. **Decision AI** — recommend strategies
3. **Execution AI** — run workflows end-to-end

MAWI is intentionally built to reach stage 3 safely through staged capability growth.

---

## 📌 Prioritization Notes

- Prioritize workflows by frequency × business impact
- Keep agent boundaries modular and testable
- Preserve context envelope as the core abstraction
- Expand autonomy only when evaluation quality is reliable
