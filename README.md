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

---

## 🧩 System Architecture

The MVP follows a multi-agent, context-centric architecture:

1. **Input / Signal Layer** — detects workflow-relevant events
2. **Context Layer** — normalizes and carries state between agents
3. **Agent Layer** — strategy, action generation, execution, and evaluation agents
4. **Tool / Action Layer** — external action adapters (email/CRM stubs)
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
Input -> Signal -> Context -> Strategy -> Action -> Approval -> Execution -> Evaluation -> Memory
```

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

```bash
python main.py
```

This runs the local demo workflow end-to-end, including approval/resume behavior.

### Web API Adapter (FastAPI)

MAWI now includes a thin web transport adapter in `api/router.py` that maps directly to `WorkflowAPI` service methods in `api/service.py` without changing service logic.

#### Endpoint Contracts

Base router prefix: `/api`

1) **Start workflow**

- **POST** `/api/workflows/start?workflow=deal-followup`
- **Default workflow selector:** `deal-followup`
- **Supported selector values:** `deal-followup` (alias) or registered workflow IDs (for example `deal_followup_workflow`)
- **Request body:**

```json
{
  "deal_id": "deal_123"
}
```

- **Response body:** context envelope dictionary returned by `WorkflowAPI.start_workflow`.

2) **List actions**

- **GET** `/api/actions?status=pending_approval`
- **Response body:**

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

- **Response body:** `{ "status": "approved", "deal_id": "...", "action_id": "..." }`

4) **Reject action**

- **POST** `/api/actions/reject`
- **Request body:**

```json
{
  "workflow": "deal-followup",
  "action_id": "act_1",
  "approver": "manager@mawi.ai",
  "reason": "Tone is too aggressive"
}
```

- **Response body:** `{ "status": "rejected", "deal_id": "...", "action_id": "...", "reason": "..." }`

5) **Edit action**

- **POST** `/api/actions/edit`
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

- **Response body:** `{ "status": "edited", "deal_id": "...", "action_id": "..." }`

6) **Get deal state**

- **GET** `/api/deals/{deal_id}`
- **Response body:** context envelope dictionary returned by `WorkflowAPI.get_deal_state`.

---

## 🤝 Contribution

This project is under active development. Contributions and feedback are welcome.
