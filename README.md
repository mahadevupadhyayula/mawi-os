# MAWI — Multi-Agent Workflow Intelligence

[![CI](https://github.com/mahadevupadhyayula/mawi-os/actions/workflows/ci.yml/badge.svg)](https://github.com/mahadevupadhyayula/mawi-os/actions/workflows/ci.yml)

> **Problem:** Business signals often become disconnected recommendations, manual handoffs, and actions with weak control or traceability.
>
> **Solution:** MAWI is a human-controlled AI workflow execution layer that turns business signals into structured decisions, approval-gated actions, and auditable outcomes.

**Project status:** Functional portfolio/reference implementation with four implemented workflows under the repository's [implementation definition](docs/workflow-contracts.md#definition-of-implemented). It uses local SQL persistence, simulated email and CRM adapters, and deterministic or optional LLM-backed modes. It is not presented as a production enterprise deployment.

> **Demo screenshot:** Not included. The repository contains a runnable local demo UI; no fabricated screenshot is shown here.

No live-demo or Loom link is listed because the repository does not provide a verified working URL.

## Quick start

Requirements: Python 3.10+ and `pip`.

```bash
git clone https://github.com/mahadevupadhyayula/mawi-os.git
cd mawi-os
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python main.py
```

Deterministic mode is the default and needs no API key. For the browser demo, follow the [containerized demo guide](docs/demo-guide.md#containerized-browser-demo).

## Core workflow

```text
Signal -> Structured context -> Decision/action plan -> Human approval -> Simulated execution -> Evaluation -> Persisted outcome
```

The orchestrator advances typed context through registered agent stages, pauses actions at the policy/approval boundary, resumes approved or rejected work, and records state and audit evidence in local SQLite.

## Three proof points

1. **Structured context and stable workflow contracts** — typed context sections and a shared prompt input contract keep handoffs inspectable across registered workflow IDs.
2. **Human approval and controlled tool execution** — approve, edit, and reject lifecycle operations gate action execution; email and CRM tools remain explicitly simulated.
3. **Deterministic fallback and auditable persistence** — offline deterministic execution is the default, invalid or unavailable optional LLM output falls back deterministically, and workflow state, actions, logs, and outcomes are persisted locally.

## Implemented workflows

“Implemented” means the repository contains a trigger, orchestrated stages, a runnable action/tool path, evaluation, and persistence. See the [workflow evidence and contracts](docs/workflow-contracts.md).

| Workflow ID | Purpose | Status |
| --- | --- | --- |
| `deal_followup_workflow` | Detect a stalled deal and prepare approval-gated follow-up | Implemented |
| `new_deal_outreach_workflow` | Prepare initial outreach for a newly created deal | Implemented |
| `deal_intervention_workflow` | Detect deal risk and prepare a controlled intervention | Implemented |
| `crm_sync_workflow` | Reconcile workflow state through the simulated CRM adapter | Implemented |

## Honest limitations

- This is a functional portfolio/reference implementation, not a production enterprise deployment.
- Persistence is local SQLite; the demo is a small, single-process deployment.
- Email and CRM adapters are simulations and do not contact real email, CRM, or customer systems.
- Hosted-demo authentication uses one shared bearer secret; there are no user accounts, OAuth, RBAC, rate limiting, or cloud infrastructure.
- LLM-backed mode is optional and makes an external model API call when enabled; it does not change approval or tool boundaries and falls back to deterministic behavior on failure.
- No performance metrics, customer outcomes, enterprise users, or production-readiness claims are asserted.

## Documentation

| Guide | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Layers, orchestration flow, persistence, and project layout |
| [Workflow contracts](docs/workflow-contracts.md) | Stable context/prompt contracts, workflow IDs, stages, and implementation evidence |
| [Demo guide](docs/demo-guide.md) | Local and container setup, scenarios, and demo operation |
| [API reference](docs/api-reference.md) | Current routes, authentication, aliases, and error model |
| [LLM fallback](docs/llm-fallback.md) | Deterministic default, optional LLM configuration, fallback, and troubleshooting |
| [Security and privacy](docs/security-and-privacy.md) | Simulation boundaries, demo controls, data, and deployment limitations |
| [Roadmap](docs/roadmap.md) | Existing future-development direction and explicit non-implementation |

Additional project records: [current workflow](current-workflow.md), [backlog](BACKLOG.md), and [test scenarios](tests/TEST_SUITE_SCENARIOS.md).

## Development

Install test tooling and run the suite:

```bash
python -m pip install -e '.[dev]'
pytest
```

Contributions and feedback are welcome. Preserve workflow IDs, context contracts, approval behavior, and persisted-state semantics when proposing changes.
