# Security and Privacy

[Back to README](../README.md) · [Demo guide](demo-guide.md) · [API reference](api-reference.md)

## Trust boundary

MAWI is a functional portfolio/reference implementation. It is not presented as a production enterprise deployment and has no enterprise users claimed by this repository.

## External actions and data

- Email sends return structured `sent_simulated` receipts from [`tools/email_tool.py`](../tools/email_tool.py).
- CRM records and activities use an in-memory simulated store in [`tools/crm_tool.py`](../tools/crm_tool.py).
- Demo fixtures are fictional JSON records under [`demo/scenarios/`](../demo/scenarios/).
- No real email, CRM, or customer system is connected.
- Optional LLM mode sends prompt data to the configured model API. Keep deterministic mode enabled when external model calls are not acceptable.

Do not load production customer or regulated data into the reference demo without an independent security, privacy, and data-governance review.

## API mutation protection

Mutation routes require bearer authentication by default:

```bash
export MAWI_API_AUTH_MODE="protected"
export MAWI_API_BEARER_TOKEN="replace-with-a-strong-token"
```

Send `Authorization: Bearer <token>`. The application refuses protected mutations when the secret is empty. The local-only bypass requires both:

```bash
export MAWI_API_AUTH_MODE="local-dev-no-auth"
export MAWI_API_ENABLE_DEV_MODE="true"
```

That bypass is for isolated development only. Demo routes additionally require `MAWI_DEMO_MODE=true`.

## Persistence

SQLite records workflow context, approval state, execution receipts, outcomes, and diagnostic/audit information. The default local file is `.mawi/mawi.db`; Compose mounts `/data/mawi.db` on the `mawi-demo-data` volume. The project does not implement encryption at rest, retention automation, tenant isolation, or production backup/restore controls.

## Known security limitations

- One shared bearer secret; no user accounts, OAuth, sessions, or RBAC.
- No rate limiting, edge protection, secret manager integration, or cloud security architecture.
- Small single-process application and local database.
- Simulated tools have not been replaced with production provider integrations.
- No claim of compliance certification, penetration testing, or production hardening.

Use a demo-specific secret, inject it at runtime, keep `.env` uncommitted, avoid real customer data, and reset canonical demo records after shared demonstrations.
