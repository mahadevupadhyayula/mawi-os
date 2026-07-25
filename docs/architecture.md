# Architecture

[Back to README](../README.md) · [Workflow and architecture diagrams](diagrams.md) · [Workflow contracts](workflow-contracts.md) · [API reference](api-reference.md)

## Design principle

MAWI executes staged business workflows with human supervision. The architecture keeps orchestration contracts, policy gates, tool boundaries, and audit records consistent between deterministic and optional LLM-backed runs.

## Architectural invariants

- Orchestration contracts remain stable across workflows and runtime modes.
- Policy and approval gates remain enforced; demo and LLM modes do not bypass them.
- Execution uses the existing adapter interfaces and produces auditable structured results.
- Invalid or unavailable LLM output falls back to deterministic stage behavior.

## Layers

1. **Input / signal** detects workflow-relevant events.
2. **Context** normalizes state into a typed envelope.
3. **Agents** provide signal, context, strategy, intervention, action, execution, CRM, and evaluation stages.
4. **Tools** expose simulated email, CRM, SMS, and deal operations.
5. **Orchestration** sequences stages, retries failures, pauses for approval, and records audit events.
6. **Memory** stores short- and long-term history and insights.
7. **Human-in-the-loop** applies policy and manages approve, edit, and reject decisions.
8. **Evaluation** scores outcomes and writes feedback artifacts.

## Execution flow

```text
Input -> Signal -> Context -> Strategy/CRM planning -> Action plan -> Approval -> Execution -> Evaluation -> Memory
```

The workflow registry supplies the ordered stages. `Orchestrator` advances the context envelope, persists snapshots and run state, and pauses when an action requires approval. Approval lifecycle operations resume or terminate that existing run rather than creating a separate business workflow.

See the reusable [business workflow and technical architecture diagrams](diagrams.md) for Mermaid views of this flow and its current implementation boundaries.

## Data and audit model

The default database path is `.mawi/mawi.db`; the container demo uses `/data/mawi.db`. Python's `sqlite3` driver backs repository abstractions for deals, workflow runs and state, versioned context envelopes, actions and steps, execution logs, outcomes, intervention/CRM logs, and prompt diagnostics.

This is local SQL persistence suitable for the reference implementation. PostgreSQL/JSONB is only a possible future replacement behind repository abstractions, not a currently implemented deployment mode.

## Project layout

```text
agents/         Specialized workflow agents and inference configuration
approval/       Approval policy, queue, and action lifecycle
api/            FastAPI transport and workflow service abstraction
context/        Context envelope and typed domain models
data/           SQLite client, models, and repositories
demo/           Fictional deterministic demo fixtures and demo service
evaluation/     Outcome analysis, metrics, and feedback artifacts
memory/         Short- and long-term stores and retrieval
orchestrator/   Runner, state machine, retries, and audit logging
tools/          Simulated action adapters
workflows/      Workflow definitions, triggers, and registry
main.py         Local command-line demo entry point
```

## Scope and maturity

MAWI is a functional portfolio/reference implementation, not a production enterprise deployment. It has no dynamic workflow builder, multi-tenant identity layer, real customer-system connectors, or cloud deployment architecture.
