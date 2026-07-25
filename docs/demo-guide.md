# Demo Guide

[Back to README](../README.md) · [API reference](api-reference.md) · [Security and privacy](security-and-privacy.md)

The demo uses fictional fixtures, deterministic agents by default, simulated email/CRM tools, and local SQLite. It does not contact a real customer system.

## Command-line demo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python main.py
```

No API key is required. This path demonstrates the local workflow including approval and resume behavior.

## Containerized browser demo

Docker and Docker Compose are required.

```bash
cp .env.example .env
# Set a strong, demo-specific MAWI_API_BEARER_TOKEN in .env.
docker compose -f docker-compose.demo.yml up --build
```

Open `http://localhost:8000/demo`, then enter the same bearer token before starting, approving, editing, rejecting, or resetting a scenario. `GET /health` provides a basic health response. There is no verified hosted demo URL in this repository.

Safe Compose defaults are `MAWI_LLM_ENABLED=false`, `MAWI_DEMO_MODE=true`, `MAWI_API_AUTH_MODE=protected`, and `MAWI_DB_PATH=/data/mawi.db`. `MAWI_PORT` changes the host port. The `mawi-demo-data` volume preserves SQLite data across container replacement.

An equivalent direct Docker run is:

```bash
docker build -t mawi-demo .
docker run --rm -p 8000:8000 \
  -e MAWI_API_BEARER_TOKEN="replace-with-a-strong-token" \
  -v mawi-demo-data:/data mawi-demo
```

## Canonical scenarios

The UI exposes three fictional fixtures from [`demo/scenarios/`](../demo/scenarios/):

- **Stalled deal approval** — starts the follow-up path and demonstrates a pending approval.
- **Rejected follow-up action** — demonstrates rejection and persisted lifecycle evidence.
- **Deterministic LLM fallback** — demonstrates recorded fallback behavior without requiring a provider call.

Scenario metadata is read-only. Mutations require bearer authentication and demo mode. Timeline, audit, and telemetry views read persisted evidence rather than invented metrics.

## Reset demo records

Use the UI reset control or:

```bash
curl -X POST \
  -H "Authorization: Bearer $MAWI_API_BEARER_TOKEN" \
  http://localhost:8000/api/demo/reset
```

The reset operation targets only canonical demo deal/run records.

## Optional LLM-backed demonstration

Set `MAWI_LLM_ENABLED=true` and provide `OPENAI_API_KEY` at runtime. This makes outbound model API calls, but email and CRM execution remains simulated, approval remains enforced, and provider/validation failure falls back to deterministic output. See [LLM fallback](llm-fallback.md).

## Suggested walkthrough

1. State the simulation and local-persistence boundaries.
2. Start a canonical scenario and inspect its ordered stage timeline.
3. Review the structured pending action and choose approve, edit, or reject.
4. Inspect the resulting audit and telemetry records.
5. Reset the fictional demo data when finished.

Do not describe telemetry durations as benchmark results or the simulated receipts as real sends/CRM writes.
