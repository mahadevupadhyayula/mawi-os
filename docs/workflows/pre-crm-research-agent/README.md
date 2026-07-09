# Pre-CRM Research Agent

Pre-CRM Research Agent is a MAWI workflow for researching, scoring, and qualifying leads before they enter CRM.

The core product question is:

> Is this lead worth pursuing, and how should we approach them?

## Why this workflow exists

Most GTM teams push leads into CRM too early. That creates noisy pipelines, weak prioritization, generic outreach, and avoidable sales work. This workflow creates a pre-CRM intelligence layer so the team can review fit, evidence, risk, buyer relevance, and next action before committing a record to CRM.

## Target users

- B2B founders
- SDR / outbound teams
- RevOps consultants
- lead generation agencies
- SaaS startups
- recruiters and consultants doing structured prospect research

## Core workflow

```text
Lead / company input
  -> ICP context
  -> company research extraction
  -> company signal context
  -> ICP evaluation and score
  -> human review gate
  -> CRM-ready payload
  -> outreach task
  -> learning update
```

## Main outputs

- lead score
- ICP fit summary
- company research summary
- likely pain points
- buying triggers
- decision-maker relevance
- suggested outreach angle
- personalized email / LinkedIn draft direction
- CRM-ready notes
- recommended next action

## Design principle

Evidence first. Signal extraction second. Evaluation third. Human approval fourth. CRM action fifth.

This prevents the workflow from prematurely qualifying bad-fit companies and keeps observed facts separate from hypotheses.

## Implementation status

Current status: `Partial / workflow contract`.

This branch adds:

- workflow contract module
- trigger registration
- registry registration
- state object schema
- prompt chain
- scoring rubric
- sample lead input
- architecture notes
- implementation roadmap

The next step is to connect the workflow stages to concrete agents, data adapters, persistence, and API routes.

## Source material

This repo implementation is based on the Notion project notes for:

- Pre-CRM Research Agent — Researching, Scoring, and Qualifying Leads Before CRM Entry
- Pre-CRM Evaluation Workflow
