# Workflow Architecture

## Architecture pattern

```text
Input -> AI Processing -> Validation -> Output -> Action / Integration
```

The Pre-CRM Research Agent is intentionally structured as a multi-step workflow rather than a single chatbot prompt. Each stage produces a structured artifact that becomes part of the workflow state.

## 1. Input layer

Collects raw information needed to evaluate a lead:

- company name
- website URL
- LinkedIn company URL
- contact name
- contact title
- industry
- location / target geography
- public source URLs
- product/service positioning
- outreach goal
- notes from user

Initial implementation can use Google Sheets or CSV input. Later versions can connect to lead lists, enrichment tools, CRM exports, and outreach tools.

## 2. ICP context layer

Defines the reusable benchmark for lead qualification.

The initial MAWI ICP focuses on early-to-growth-stage B2B SaaS or B2B tech-enabled companies with sales-led or demo-led GTM motions, active pipeline, CRM/email usage, and workflow pain around follow-ups, stalled deals, CRM hygiene, and next-best-action execution.

## 3. Company research and signal extraction layer

Creates a company signal context artifact without judging fit yet.

Research areas:

- company identity
- business model
- product category
- target customer
- sales motion
- company size and stage
- GTM team evidence
- tooling and data readiness
- GTM pain signals
- urgency triggers
- buyer access

## 4. Evaluation and scoring layer

Compares the company signal context against the ICP context.

The scoring model totals 100 points:

- firmographic ICP fit: 20
- sales motion fit: 20
- GTM pain intensity: 25
- tool/data readiness: 15
- urgency trigger strength: 10
- buyer accessibility: 10

## 5. Validation and guardrail layer

Prevents over-inference and premature CRM creation.

Guardrails:

- source grounding for important claims
- confidence levels
- unknown field handling
- evidence vs hypothesis separation
- duplicate / existing-record checks
- low-confidence flags
- human review before CRM action

## 6. Human review gate

Creates a concise review packet with:

- ICP score
- fit level
- strongest evidence
- weakest evidence
- biggest risk
- recommended buyer
- recommended MAWI workflow
- first outreach angle

Allowed human decisions:

- approve_add_to_crm
- reject
- research_more
- add_to_watchlist
- manual_review_later

## 7. CRM payload layer

Only runs after approval.

Creates a structured CRM-ready account payload with qualification, buyer, outreach, evidence, and next-action fields.

## 8. Outreach task layer

Converts qualification into the first GTM action.

The output is not a long email by default. It is a task brief that a rep or later Outreach Agent can use.

## 9. Learning and memory layer

Captures downstream outcome data and turns it into reusable learning.

Possible outcomes:

- company added to CRM
- human rejected recommendation
- more research requested
- outreach sent
- buyer replied
- meeting booked
- wrong buyer identified
- ICP score later confirmed accurate or inaccurate

## Workflow continuity model

```text
Company Input
   ↓
ICP Context
   ↓
Company Research Notes
   ↓
Company Signal Context Artifact
   ↓
Pre-CRM Evaluation
   ↓
Human Review Gate
   ↓
CRM Payload
   ↓
CRM Writeback
   ↓
Outreach Task
   ↓
Learning Update
```
