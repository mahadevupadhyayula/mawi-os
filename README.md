# SaaS Sales Multi-Agent Workflow System

Production-style modular Python implementation for stalled-deal follow-up automation with HITL approval.

## Folder map
- `context/`: ContextEnvelope schema, merge rules, trigger validation.
- `agents/`: six strict agents (`signal`, `context`, `strategist`, `action`, `execution`, `evaluator`).
- `tools/`: simulated tool adapters (`fetch_deal_data`, `send_email`, `update_crm`).
- `orchestrator/`: workflow engine, retries, stage logging, dead-letter.
- `workflows/`: trigger and workflow entrypoint.
- `memory/`: short-term and long-term stores.
- `evaluation/`: comparison, insight generation, metrics.
- `api/`: UI-ready endpoint handlers and route map.

## Run example workflow
```bash
python main.py
```

## Run orchestrator example
```bash
python orchestrator/runner.py
```

## Run API usage simulation
```bash
python example_usage.py
```

## Notes
- Uses append/refine context updates only.
- Each agent updates only its own context section.
- Approval queue is enforced when action confidence is below threshold.
