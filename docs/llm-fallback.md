# Deterministic and LLM-Backed Modes

[Back to README](../README.md) · [Workflow contracts](workflow-contracts.md) · [Demo guide](demo-guide.md)

## Deterministic default

`MAWI_LLM_ENABLED=false` is the safe, offline default. No provider key is required. It is the preferred mode for local development, regression tests, and repeatable demonstrations.

Deterministic and LLM-backed runs use the same workflow IDs, context and output contracts, orchestrator stages, policy/approval gate, simulated execution tools, and audit/persistence paths.

## Optional LLM mode

Install the existing project dependencies, then configure the runtime environment:

```bash
export MAWI_LLM_ENABLED=true
export OPENAI_API_KEY="sk-..."
export MAWI_LLM_PROVIDER="openai"
export MAWI_OPENAI_MODEL="gpt-4.1-mini"
export MAWI_LLM_MODEL="gpt-4.1-mini"  # alias used if MAWI_OPENAI_MODEL is unset
export MAWI_LLM_TIMEOUT_SEC="30"
export MAWI_LLM_MAX_RETRIES="2"
export MAWI_LLM_RETRY_BACKOFF_SEC="0.6"
export MAWI_LLM_TEMPERATURE="0.0"
export MAWI_LLM_BASE_URL="https://api.openai.com"
```

An enabled provider makes external model API requests. It does not enable real email or CRM integrations.

## Runtime precedence

`RuntimeLLMConfig` is the runtime configuration source passed into agent inference. Explicit timeout and retry values on an `LLMRequest` take precedence over environment-derived fallback defaults. See [`agents/runtime_config.py`](../agents/runtime_config.py) and [`agents/llm_client.py`](../agents/llm_client.py).

## Fallback behavior

Model output is validated against the stage contract. Provider errors, timeouts, invalid JSON, or invalid contract output are recorded and cause that stage to use its deterministic payload. The run continues through the existing orchestration and policy boundaries; fallback is not an approval bypass.

## Troubleshooting

### Invalid JSON or missing fields

- **Observed behavior:** validation fails and the stage records fallback before returning deterministic output.
- **Check:** prompt contract fields and provider response; keep temperature at `0.0` for predictable structured generation.

### Timeout

- **Observed behavior:** the client retries up to `MAWI_LLM_MAX_RETRIES`, then falls back.
- **Check:** provider availability and `MAWI_LLM_TIMEOUT_SEC`, or use deterministic mode for offline demos.

### Missing API key

- **Observed behavior:** an enabled provider cannot complete and the agent falls back.
- **Check:** provide a runtime key or set `MAWI_LLM_ENABLED=false`. Never commit a real key.

Fallback provides execution continuity and auditability, not a claim that generated output is equivalent to provider output.
