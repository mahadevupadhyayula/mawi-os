# MAWI — Multi-Agent Workflow Intelligence

## 🚀 What is MAWI?

MAWI is a **Multi-Agent AI Workflow Engine** designed to execute end-to-end business workflows with human-in-the-loop control.

Unlike traditional tools that only analyze data or suggest next steps, MAWI is designed to:

- detect signals
- make decisions
- generate and execute actions
- learn from outcomes

---

## 🧠 Core Philosophy

MAWI is built on one principle:

> AI should not just assist workflows — it should execute them with human supervision.

This is enabled through:

- modular specialized agents
- structured context envelopes
- tool-driven execution
- evaluation and memory feedback loops

### Architectural Invariants (Always On)

The following principles remain explicit and non-negotiable across deterministic and LLM-backed runs:

- **orchestration contracts remain stable** across workflows and rollout stages
- **policy/approval gate is always enforced** (no bypass in demo modes)
- **execution tools stay unchanged and auditable** through existing adapters and audit logs
- **fallback-to-deterministic behavior preserves runtime safety** when LLM output is unavailable or invalid

---

## 🧩 System Architecture

MAWI uses a staged rollout model while preserving one shared multi-agent architecture.

### Stage 1 / 2 / 3 Rollout Model

- **Stage 1 (MVP execution wedge):** deal follow-up + new-deal outreach, human approval gate by default, basic evaluation/memory loop.
- **Stage 2 (deal intelligence expansion):** adds risk/intervention and CRM synchronization workflows on the same orchestrator contracts.
- **Stage 3 (autonomous platform):** planned guardrailed autonomy, dynamic orchestration, and cross-deal optimization.

### Shared Architecture Layers

1. **Input / Signal Layer** — detects workflow-relevant events
2. **Context Layer** — normalizes and carries state between agents
3. **Agent Layer** — strategy, action generation, execution, CRM, and evaluation agents
4. **Tool / Action Layer** — external action adapters (email/CRM/SMS/deal systems)
5. **Orchestration Layer** — stage sequencing, retries, audit logging
6. **Memory Layer** — short- and long-term storage for history and insights
7. **Human-in-the-loop Layer** — approval policies and action queue
8. **Evaluation Layer** — outcome scoring and feedback generation

---

## 🎯 MVP Scope

The MVP is intentionally focused on a single wedge use case:

### **SaaS Sales Deal Follow-up Execution**

Primary objective:

👉 prove that AI-driven workflow execution can improve pipeline velocity on stalled deals.

### Included in MVP

- stalled-deal signal detection
- strategy recommendation
- follow-up email/action generation
- confidence-aware human approval
- simulated execution through tools
- post-action evaluation and memory write-back

### Definition of Implemented (MVP)

A workflow is considered **Implemented** only when all of the following are present:

1. **Trigger** — concrete event/signal detection exists.
2. **Orchestration** — workflow is sequenced by the orchestrator.
3. **Execution** — at least one action/tool path is runnable.
4. **Evaluation** — outcomes are analyzed/scored after execution.
5. **Persistence** — state/outcomes are persisted for resume/audit.

If one or more criteria are incomplete, the workflow is **Partial**.

### Explicitly Out of Scope (for MVP)

- full autonomous no-approval mode
- multi-channel orchestration at scale
- advanced forecasting and optimization systems

---

## ⚙️ MVP Functionalities

### 1) Deal Follow-up Workflow

- detect inactive/stalled deal conditions
- produce strategy + outreach action
- queue actions for approval
- resume workflow after approve/reject

### 2) AI Action Generation

- context-aware outbound drafts
- persona/objection-aware messaging patterns
- confidence-scored outputs for routing decisions

### 3) Human-in-the-loop Control

- approve / edit / reject gate before execution
- policy checks for confidence thresholds
- auditable lifecycle history

### 4) Context Engine

- structured envelope with typed sections
- stage-by-stage updates rather than ad hoc payloads
- predictable handoff contract between components

### 5) Orchestration Engine

- sequential runner for MVP stage flow
- retry and audit hooks
- deterministic state progression

### 6) Tool Integration (Simulated in MVP)

- email dispatch adapter
- CRM update adapter
- standardized execution result payloads

### 7) Evaluation & Learning Loop (Basic)

- capture execution + reply outcomes
- generate initial insights
- persist insights to memory stores
- apply staged memory-quality gates and adaptation telemetry for auditable feedback decisions

## ✅ Current Workflow Implementation Status

Only workflows with end-to-end code evidence are marked **Implemented**.

- **SaaS Sales Deal Follow-up Execution (`deal_followup_workflow`)** — **Implemented**.
  - Trigger: [`workflows/triggers.py`](./workflows/triggers.py)
  - Workflow definition + stages: [`workflows/deal_followup_workflow.py`](./workflows/deal_followup_workflow.py)
  - Orchestration + state progression: [`orchestrator/runner.py`](./orchestrator/runner.py), [`orchestrator/state_machine.py`](./orchestrator/state_machine.py)
  - Execution paths/tools: [`agents/execution_agent.py`](./agents/execution_agent.py), [`tools/email_tool.py`](./tools/email_tool.py), [`tools/crm_tool.py`](./tools/crm_tool.py), [`tools/deal_tool.py`](./tools/deal_tool.py)
  - Evaluation loop: [`agents/evaluator_agent.py`](./agents/evaluator_agent.py), [`evaluation/outcome_analyzer.py`](./evaluation/outcome_analyzer.py), [`evaluation/metrics.py`](./evaluation/metrics.py)
  - Persistence + audit trail: [`data/repositories/workflow_repo.py`](./data/repositories/workflow_repo.py), [`data/repositories/action_repo.py`](./data/repositories/action_repo.py), [`data/repositories/outcome_repo.py`](./data/repositories/outcome_repo.py), [`orchestrator/audit_logger.py`](./orchestrator/audit_logger.py)
  - API orchestration entry points: [`api/service.py`](./api/service.py), [`api/router.py`](./api/router.py)

- **New Deal Outreach (`new_deal_outreach_workflow`)** — **Implemented**.
  - Trigger: [`workflows/triggers.py`](./workflows/triggers.py)
  - Workflow definition + stages: [`workflows/new_deal_outreach_workflow.py`](./workflows/new_deal_outreach_workflow.py)
  - Registry exposure: [`workflows/registry.py`](./workflows/registry.py)
  - Orchestration, execution, evaluation, and persistence path: same core modules as deal follow-up (runner, execution agent, evaluator, and repositories listed above).

- **Deal Intervention (`deal_intervention_workflow`)** — **Implemented**.
  - Trigger + thresholds: [`workflows/triggers.py`](./workflows/triggers.py)
  - Workflow definition + stages: [`workflows/deal_intervention_workflow.py`](./workflows/deal_intervention_workflow.py)
  - Registry exposure: [`workflows/registry.py`](./workflows/registry.py)
  - API run path + intervention logging: [`api/router.py`](./api/router.py), [`api/service.py`](./api/service.py), [`data/repositories/intervention_log_repo.py`](./data/repositories/intervention_log_repo.py)

- **CRM Sync (`crm_sync_workflow`)** — **Implemented**.
  - Trigger + post-action/API trigger contract: [`workflows/triggers.py`](./workflows/triggers.py)
  - Workflow definition + stages: [`workflows/crm_sync_workflow.py`](./workflows/crm_sync_workflow.py)
  - Registry exposure: [`workflows/registry.py`](./workflows/registry.py)
  - API run path + sync-status/logging: [`api/router.py`](./api/router.py), [`api/service.py`](./api/service.py), [`data/repositories/crm_sync_log_repo.py`](./data/repositories/crm_sync_log_repo.py)

- **Planned workflows not listed above** — **Not Implemented** unless explicitly stated in [`current-workflow.md`](./current-workflow.md) and backed by code.

### Implemented Workflow Update Policy

Update this section immediately when a workflow first satisfies all implementation criteria:

1. Trigger
2. Orchestration
3. Execution
4. Evaluation
5. Persistence

When promoting a workflow to **Implemented**, include concrete cross-links to the module files that satisfy each criterion.

---

## 🧱 Project Structure

```text
/agents         # Specialized workflow agents (signal, strategy, action, execution, evaluation)
/approval       # Human approval queue, policy, and lifecycle
/api            # Application service interface for callers/UI
/context        # Context envelope and typed domain models
/evaluation     # Outcome analysis, metrics, and feedback artifacts
/memory         # Short/long-term memory stores and retrieval
/orchestrator   # Runner, state machine, retry policy, audit logging
/tools          # External action adapters (email, CRM, deal systems)
/workflows      # Workflow definitions, triggers, registry
main.py         # Local demo entrypoint
```

---

## 🔁 Workflow Execution Flow

```text
Input -> Signal -> Context -> Strategy/CRM Planning -> Action Plan -> Approval (policy) -> Execution -> Evaluation -> Memory
```

### Stage-specific runtime paths

- **Stage 1 default path** (`deal_followup_workflow`, `new_deal_outreach_workflow`):
  `signal_agent -> context_agent -> strategist_agent -> action_agent -> execution_agent -> evaluator_agent`
- **Stage 2 intervention path** (`deal_intervention_workflow`):
  `signal_agent -> context_agent -> strategist_agent -> action_agent -> execution_agent -> evaluator_agent`
- **Stage 2 CRM sync path** (`crm_sync_workflow`):
  `signal_agent -> context_agent -> crm_agent -> execution_agent -> evaluator_agent`

---

## 🧠 Context System (Core Differentiator)

MAWI relies on a structured context envelope with sections such as:

- `meta`
- `signal_context`
- `deal_context`
- `decision_context`
- `action_context`
- `execution_context`
- `outcome_context`

Design rule:

👉 context evolves through explicit stage updates so every decision remains inspectable and debuggable.

### Prompt Input Contract (Standardized Across Agents)

All agent prompt renders now require a common contract so behavior can adapt by workflow and stage.

Required contract fields:

- `workflow_id` (defaults to `deal_followup_workflow` when omitted)
- `workflow_goal`
- `stage_name`
- `policy_mode`
- `expected_output_schema`

If any required key except `workflow_id` is missing, prompt rendering fails fast and prompt execution is blocked.

#### Contract examples by current agent

```json
{
  "agent": "signal_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Detect stalled-deal triggers for follow-up workflows.",
  "stage_name": "signal_agent",
  "policy_mode": "observe_only",
  "expected_output_schema": "SignalContext(stalled, days_since_reply, urgency, trigger_reason, reasoning, confidence)"
}
```

```json
{
  "agent": "context_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Build normalized deal context for downstream strategy and action agents.",
  "stage_name": "context_agent",
  "policy_mode": "observe_only",
  "expected_output_schema": "DealContext(persona, deal_stage, known_objections, recent_timeline, recommended_tone, reasoning, confidence)"
}
```

```json
{
  "agent": "strategist_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Select a next-best strategy that restarts stalled conversations.",
  "stage_name": "strategist_agent",
  "policy_mode": "policy_guided",
  "expected_output_schema": "DecisionContext(strategy_id, strategy_type, message_goal, fallback_strategy, memory_evidence_used, memory_confidence_impact, memory_rationale, reasoning, confidence)"
}
```

```json
{
  "agent": "action_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Generate an ordered, approval-ready action plan from strategy and deal context.",
  "stage_name": "action_agent",
  "policy_mode": "policy_guided",
  "expected_output_schema": "ActionPlanContext(plan_id, steps[], status, reasoning, confidence)"
}
```

```json
{
  "agent": "execution_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Execute approved action steps through channel adapters with policy enforcement.",
  "stage_name": "execution_agent",
  "policy_mode": "enforced",
  "expected_output_schema": "ExecutionContext(execution_id, status, email_result, crm_result, tool_events, reasoning, confidence)"
}
```

```json
{
  "agent": "evaluator_agent",
  "workflow_id": "deal_followup_workflow",
  "workflow_goal": "Evaluate execution outcomes and produce reusable learning signals.",
  "stage_name": "evaluator_agent",
  "policy_mode": "observe_only",
  "expected_output_schema": "OutcomeContext(outcome_label, insight, recommended_adjustment, reasoning, confidence)"
}
```

---

## ⚡ Human-in-the-Loop Design

- lower confidence actions require approval
- higher confidence paths can graduate toward auto-execution in future phases
- all actions are traceable through queue/lifecycle/audit records

---


## 🗄️ Data Layer

MAWI includes a persistent data layer for MVP operations to:

- track workflow state across restarts
- store actions, approvals, execution logs, and outcomes
- persist context envelope snapshots for resume/debug

Current implementation uses a local SQL store for out-of-the-box execution and repository abstractions that can be upgraded to PostgreSQL/JSONB in production.

---

## 🚀 Future Development Goals

### Phase 2 — Deal Intelligence System

- richer risk detection workflows
- intervention and objection-handling playbooks
- multi-channel outreach sequencing
- deeper memory and persona adaptation

### Phase 3 — Autonomous Workflow Engine

- guarded auto-execution mode
- dynamic workflow composition/builder
- reinforcement-style learning loops
- cross-deal optimization and forecasting

For detailed roadmap items, see [`BACKLOG.md`](./BACKLOG.md).

---

## 🛠️ Getting Started

### Environment Setup (Deterministic + LLM-backed)

MAWI runs safely by default in deterministic mode with no external API dependency.

```bash
# Optional but recommended: create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate
```

### Install dependencies

From a clean checkout, install runtime dependencies (and optional test tooling) with:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
# Optional: install test/dev extras
python -m pip install -e .[dev]
```

#### Required for live LLM mode

```bash
export OPENAI_API_KEY="sk-..."
```

#### Optional `MAWI_LLM_*` runtime controls

```bash
# Keep deterministic mode (safe/offline default)
export MAWI_LLM_ENABLED=false

# Enable live LLM mode
# export MAWI_LLM_ENABLED=true

# Provider/model/runtime controls
export MAWI_LLM_PROVIDER="openai"
export MAWI_OPENAI_MODEL="gpt-4.1-mini"
export MAWI_LLM_MODEL="gpt-4.1-mini"        # fallback alias if MAWI_OPENAI_MODEL unset
export MAWI_LLM_TIMEOUT_SEC="30"
export MAWI_LLM_MAX_RETRIES="2"
export MAWI_LLM_RETRY_BACKOFF_SEC="0.6"
export MAWI_LLM_TEMPERATURE="0.0"
export MAWI_LLM_BASE_URL="https://api.openai.com"
```

`RuntimeLLMConfig` is the single source of truth for runtime retries/timeouts inside agent execution.

- `runtime_config.timeout_sec` and `runtime_config.max_retries` are passed explicitly to each `LLMRequest`.
- Environment values (`MAWI_LLM_TIMEOUT_SEC`, `MAWI_LLM_MAX_RETRIES`, `MAWI_LLM_RETRY_BACKOFF_SEC`) are used to *build* `RuntimeLLMConfig`, and remain a fallback only when an `LLMRequest` omits those fields directly.
- Effective precedence for retry/timeout is: **explicit `LLMRequest` values > env fallback defaults**.

### Demo modes

#### Mode A — deterministic (safe/offline)

- `MAWI_LLM_ENABLED=false` (default) keeps agent outputs deterministic.
- No `OPENAI_API_KEY` is required.
- Best for local development, regression tests, and auditable baseline behavior.
- Orchestration contracts, approval gating, and execution-tool audit traces remain identical to live mode.

#### Mode B — live LLM (investor/customer demos)

- Set `MAWI_LLM_ENABLED=true` and provide `OPENAI_API_KEY`.
- Uses OpenAI-backed JSON generation while preserving the same orchestrator + policy controls.
- If the model call fails validation or runtime checks, MAWI automatically falls back to deterministic payloads.
- Recommended for narrative-rich demos where you want dynamic phrasing but stable workflow safety.

```bash
python main.py
```

This runs the local demo workflow end-to-end, including approval/resume behavior.

### Troubleshooting LLM-backed runs

- **Invalid JSON from provider**
  - Symptom: LLM result cannot be parsed as JSON or misses required fields.
  - Behavior: MAWI logs validation/provider fallback and uses deterministic output for that stage.
  - Action: keep `MAWI_LLM_TEMPERATURE=0.0`, verify prompt contract fields, and keep retries enabled.

- **Timeouts**
  - Symptom: provider calls exceed `MAWI_LLM_TIMEOUT_SEC`.
  - Behavior: MAWI retries up to `MAWI_LLM_MAX_RETRIES`, then falls back to deterministic output.
  - Action: increase timeout, reduce model latency risk, or keep deterministic mode for offline demos.

- **Missing API key**
  - Symptom: `OPENAI_API_KEY` is unset while `MAWI_LLM_ENABLED=true`.
  - Behavior: provider error is returned and agent stage falls back to deterministic output.
  - Action: export a valid key or set `MAWI_LLM_ENABLED=false`.

- **Fallback behavior (expected safety path)**
  - MAWI preserves execution continuity by using deterministic stage payloads when LLM output is invalid/unavailable.
  - Approval/policy gates and tool execution boundaries remain enforced and auditable during fallback.

### Web API Adapter (FastAPI)

MAWI includes a thin web transport adapter in `api/router.py` that maps directly to `WorkflowAPI` service methods in `api/service.py`.

#### Endpoint Contracts

Base router prefix: `/api`

#### Mutation Endpoint Authentication

Mutation endpoints (write/execute operations) now require bearer auth by default, including:

- `POST /api/workflows/start`
- `POST /api/actions/approve`
- `POST /api/actions/reject`
- `POST /api/actions/edit`
- `POST /api/workflows/intervention/run`
- `POST /api/workflows/crm-sync/run`

Use these environment variables:

```bash
# Default: protected mode (recommended for shared/hosted demos)
export MAWI_API_AUTH_MODE="protected"
export MAWI_API_BEARER_TOKEN="replace-with-a-strong-token"
```

Send requests with:

```http
Authorization: Bearer <your-token>
```

For local development only, you can explicitly bypass auth:

```bash
export MAWI_API_AUTH_MODE="local-dev-no-auth"
export MAWI_API_ENABLE_DEV_MODE="true"
```

The bypass requires both variables so auth is not disabled accidentally in shared environments.

#### Error Model

When a workflow, action, or deal state cannot be resolved, endpoints return a consistent JSON error payload:

```json
{
  "error": "unknown_workflow",
  "message": "Unknown workflow name: foo"
}
```

Known error values:

- `unknown_workflow` (HTTP 400)
- `action_not_found` (HTTP 404)
- `deal_state_not_found` (HTTP 404)

1) **Start workflow**

- **POST** `/api/workflows/start?workflow=deal-followup`
- **Also supported:**
  - alias `workflow=crm-sync`
  - explicit workflow IDs: `deal_followup_workflow`, `new_deal_outreach_workflow`, `deal_intervention_workflow`, `crm_sync_workflow`
- **Maps to:** `WorkflowAPI.start_workflow(deal_id, workflow_name=...)`
- **Workflow validation:** query value is alias-resolved then checked with `is_known_workflow`.
- **CRM sync note:** when `workflow=crm-sync` (or `crm_sync_workflow`) the API injects explicit trigger context (`trigger_source=api`, `trigger_event=explicit`).
- **Request body:**

```json
{
  "deal_id": "deal_123"
}
```

- **Success response (200):** full context envelope dictionary from `WorkflowAPI.start_workflow`.
- **Error example (400):**

```json
{
  "error": "unknown_workflow",
  "message": "Unknown workflow name: invalid-workflow"
}
```

2) **List actions**

- **GET** `/api/actions?status=pending_approval`
- **Maps to:** `WorkflowAPI.get_actions(status=...)`
- **Success response (200):**

```json
{
  "actions": [
    {
      "action_id": "act_1",
      "status": "pending_approval"
    }
  ]
}
```

3) **Approve action**

- **POST** `/api/actions/approve`
- **Maps to:** `WorkflowAPI.approve_action(...)`
- **Workflow validation:** body field `workflow` must resolve to a known workflow.
- **Request body:**

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "manager@mawi.ai",
  "reply_received": true,
  "meeting_booked": false
}
```

- **Success response (200):**

```json
{
  "status": "approved",
  "deal_id": "deal_123",
  "action_id": "act_1"
}
```

- **Error example (404):**

```json
{
  "error": "action_not_found",
  "message": "Action not found"
}
```

4) **Reject action**

- **POST** `/api/actions/reject`
- **Maps to:** `WorkflowAPI.reject_action(...)`
- **Workflow validation:** body field `workflow` must resolve to a known workflow.
- **Request body:**

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "manager@mawi.ai",
  "reason": "Tone is too aggressive"
}
```

- **Success response (200):**

```json
{
  "status": "rejected",
  "deal_id": "deal_123",
  "action_id": "act_1",
  "reason": "Tone is too aggressive"
}
```

5) **Edit action**

- **POST** `/api/actions/edit`
- **Maps to:** `WorkflowAPI.edit_action(...)`
- **Workflow validation:** body field `workflow` must resolve to a known workflow.
- **Request body:**

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "manager@mawi.ai",
  "preview": "Updated subject line",
  "body_draft": "Refined body copy"
}
```

- **Success response (200):**

```json
{
  "status": "edited",
  "deal_id": "deal_123",
  "action_id": "act_1"
}
```

6) **Get deal state**

- **GET** `/api/deals/{deal_id}`
- **Maps to:** `WorkflowAPI.get_deal_state(deal_id)`
- **Success response (200):** full context envelope dictionary.
- **Error example (404):**

```json
{
  "error": "deal_state_not_found",
  "message": "Deal state not found"
}
```

7) **Run intervention workflow (explicit endpoint)**

- **POST** `/api/workflows/intervention/run`
- **Maps to:** `WorkflowAPI.run_intervention_workflow(deal_id)`
- **Success response (200):** returns a workflow envelope with `workflow_id=deal_intervention_workflow`.

8) **Run CRM sync workflow (explicit endpoint)**

- **POST** `/api/workflows/crm-sync/run`
- **Maps to:** `WorkflowAPI.run_crm_sync_workflow(deal_id)`
- **Success response (200):** returns a workflow envelope with `workflow_id=crm_sync_workflow`.

9) **Get CRM sync status**

- **GET** `/api/crm/sync-status?deal_id=...` (or `run_id=...`)
- **Maps to:** `WorkflowAPI.get_crm_sync_status(deal_id=..., run_id=...)`
- **Success response (200):** includes `sync_status`, `synced_at`, `error_message`, and `updated_at`.

---

## 🔄 API Migration Notes

Add a short migration note here whenever API method signatures, request/response schemas, or endpoint contracts change in a way that may impact callers.

Template:

- **Date (YYYY-MM-DD)** — `component`
  - **Change:** what signature/contract changed.
  - **Action required:** what downstream callers must update.
  - **Compatibility:** backward-compatible or breaking.

- **2026-04-14** — `api/router.py`
  - **Change:** mutation endpoints now enforce bearer-token authentication by default.
  - **Action required:** set `MAWI_API_BEARER_TOKEN` and send `Authorization: Bearer <token>` for protected deployments; for local-only demos, explicitly set `MAWI_API_AUTH_MODE=local-dev-no-auth` and `MAWI_API_ENABLE_DEV_MODE=true`.
  - **Compatibility:** backward-compatible for local dev with explicit bypass; behavior change for unprotected hosted endpoints.

---

## 🧾 Compatibility Changelog

Track only compatibility-impacting behavior here (API signatures, persisted schema contracts, lifecycle status semantics, or workflow stage contract changes).

- **2026-04-14** — API mutation auth defaults to bearer-token protection with explicit local-dev bypass toggle (`MAWI_API_AUTH_MODE` + `MAWI_API_ENABLE_DEV_MODE`).

- **2026-04-11** — Documentation policy added for:
  - immediate `Implemented Workflows` updates once a workflow meets full criteria;
  - strict backlog status promotion only after trigger + orchestration + execution + evaluation + persistence are all present;
  - required module cross-links for each implemented workflow;
  - required migration-note entries when API signatures evolve.

---

## 🤝 Contribution

This project is under active development. Contributions and feedback are welcome.
