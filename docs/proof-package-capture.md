# Proof-package capture guide

This guide prepares a repeatable set of six screenshots and a 60–90 second Loom walkthrough. It does **not** capture or record media. The browser demo uses fictional fixtures, local persistence, and simulated email/CRM tools.

## Capture profiles

Use two local runs. The first is the canonical stalled-deal story in the default deterministic mode. The second intentionally enables the optional LLM path without a key so the local client records a provider configuration failure and falls back before making a network request.

### Profile A: canonical stalled-deal run

1. Create the local environment and start the demo exactly as described in [the demo guide](demo-guide.md#containerized-browser-demo). Keep `MAWI_LLM_ENABLED=false` and set a demo-only `MAWI_API_BEARER_TOKEN` in `.env`.
2. Open `http://localhost:8000/demo`, enter the bearer token, click **Reset demo**, and select **Stalled deal approval**.
3. Click **Start workflow**. Confirm the page shows deal `demo-stalled-aster-labs`, workflow `deal_followup_workflow`, current stage `waiting_approval`, and approval state `pending_approval`.
4. Capture screenshots 1–3 before approving. Do not edit the proposed message; this keeps the fixture-derived state repeatable.
5. Click **Approve & simulate execution**, wait for the success message, and confirm the current stage is `evaluation_done`. Capture screenshots 4–5.

The canonical fictional story is Aster Labs, a proposal-stage deal with Riley Example (VP Sales), eight days since reply, and the objections `budget timing` and `integration risk`. The signal leads to a drafted follow-up that must remain behind human approval until the reviewer acts. Approval then runs only the simulated email and CRM tools, followed by evaluation and memory write-back.

### Profile B: controlled LLM-failure run

1. Stop Profile A. In `.env`, set `MAWI_LLM_ENABLED=true` and leave `OPENAI_API_KEY` unset or empty. Keep the same demo-only bearer token. Restart the demo containers.
2. Open `http://localhost:8000/demo`, enter the bearer token, click **Reset demo**, select **Deterministic LLM fallback**, and click **Start workflow**.
3. Confirm the runtime says `LLM-assisted`; **Run telemetry** says `Fallback used`; the fallback reason includes `llm_error:provider_error`; and the Signal timeline card says `fallback used`. Capture screenshot 6.
4. Restore `MAWI_LLM_ENABLED=false` after capture. Never substitute a real credential for this controlled failure profile.

With no `OPENAI_API_KEY`, the client returns a structured error before constructing an outbound provider request. This is a controlled configuration-failure demonstration, not a provider availability test and not the fixture's test-only invalid-JSON injection.

## Screenshot list

Use a clean browser profile at a consistent desktop viewport (recommended: 1440 × 900 at 100% zoom). Crop to the named UI sections rather than including the entire browser. Keep the footer or the header simulation statement visible whenever practical.

### 1. Deal signal

- **Scenario state:** Profile A, immediately after **Start workflow**, before approval.
- **UI section:** **Workflow summary** plus timeline cards **01 · Signal** and **02 · Context**.
- **Fields that must be visible:** Deal ID `demo-stalled-aster-labs`; workflow ID `deal_followup_workflow`; trigger `no_reply_5_days`; urgency; current stage `waiting_approval`; Signal status/confidence/mode; Context status/confidence/mode.
- **Fields that must be hidden:** bearer-token input; browser developer tools; raw run data; environment values; unrelated scenario controls if they make the text illegible.
- **Caption:** “A fictional stalled proposal produces a structured signal and enters the deterministic follow-up workflow.”
- **Claim supported:** MAWI detects the canonical stalled-deal signal and records its trigger, urgency, and workflow state.

### 2. Structured context and strategy

- **Scenario state:** Profile A, still pending approval.
- **UI section:** **Workflow timeline**, centered on **02 · Context**, **03 · Strategy**, and **04 · Action**. Open **Raw run data** only if the named structured fields cannot be legibly shown from the cards.
- **Fields that must be visible:** Context, Strategy, and Action card names; their completed state, confidence, and `deterministic` mode. If using raw data, show only `deal_context` (`persona`, `deal_stage`, `known_objections`, `recommended_tone`) and `decision_context` (`strategy_id`, `strategy_type`, `message_goal`, `fallback_strategy`, `memory_rationale`).
- **Fields that must be hidden:** bearer token; raw-data metadata timestamps and IDs not needed for the claim; history payloads; credentials or environment values; approval controls.
- **Caption:** “Typed deal context informs a deterministic strategy and a structured follow-up draft.”
- **Claim supported:** MAWI preserves structured context and strategy evidence before proposing an action.

### 3. Approval queue

- **Scenario state:** Profile A, pending approval and before any execution.
- **UI section:** **Approval required**, with the **Workflow summary** approval state visible if the viewport permits.
- **Fields that must be visible:** `Awaiting reviewer`; policy-review reason; proposed subject; proposed body; confidence; **Approve & simulate execution**; approval state `pending_approval` when included.
- **Fields that must be hidden:** bearer-token input; rejection-reason input (crop it out unless demonstrating rejection); raw run data; any real recipient address; browser autofill suggestions.
- **Caption:** “The fictional follow-up remains queued for explicit human review before simulated execution.”
- **Claim supported:** Human approval gates the proposed external action.

### 4. Execution trace

- **Scenario state:** Profile A, immediately after **Approve & simulate execution** completes.
- **UI section:** **Outcome**, focused on **Simulated email result**, **Simulated CRM result**, and **Tool events**; include the `Simulated tools only` badge.
- **Fields that must be visible:** simulated email result; simulated CRM result; tool-event records; the `Simulated tools only` label. If space permits, include Run telemetry values `Approval decision`, `Execution`, and `Tool events`.
- **Fields that must be hidden:** bearer token; raw run data; environment values; any claim or annotation implying a real send or CRM write; workflow-duration values if they could be mistaken for benchmarks.
- **Caption:** “After approval, MAWI records simulated email and CRM tool events—no customer system is connected.”
- **Claim supported:** Approved actions produce an auditable simulated execution trace.

### 5. Evaluation and memory

- **Scenario state:** Profile A, after simulated execution and evaluation.
- **UI section:** **Outcome**, focused on **Outcome label**, **Evaluator insight**, **Recommended adjustment**, and **Memory write-back**. Optionally include timeline cards **07 · Evaluation** and **08 · Memory**.
- **Fields that must be visible:** outcome label; evaluator insight; recommended adjustment; memory write-back statement; Evaluation and Memory completed states when included.
- **Fields that must be hidden:** bearer token; workflow-duration values; raw internal history; invented metrics; annotations suggesting measured customer or revenue impact.
- **Caption:** “The simulated result is evaluated and its insight is written back for future persona-level retrieval.”
- **Claim supported:** The completed run persists evaluation evidence and a memory write-back.

### 6. LLM failure with deterministic fallback

- **Scenario state:** Profile B, **Deterministic LLM fallback** started and waiting for approval; do not approve it.
- **UI section:** **Run telemetry** plus timeline card **01 · Signal**.
- **Fields that must be visible:** Runtime `LLM-assisted`; `Fallback used`; fallback reason `llm_error:provider_error`; error class `provider_error`; Signal card's `fallback used` marker; current stage `waiting_approval` if space permits.
- **Fields that must be hidden:** bearer token; all environment values; raw response text; raw run data; any `OPENAI_API_KEY` field; unrelated duration values.
- **Caption:** “A controlled missing-key failure is recorded and the workflow continues with deterministic output without a provider request.”
- **Claim supported:** Optional LLM failure is observable while deterministic fallback preserves the approval-gated workflow.

## Loom storyboard (90 seconds)

Record Profile A first, then cut to the already-prepared Profile B tab for the final segment. Do not type a token or edit environment files on screen.

| Time | View | Narration cue |
| --- | --- | --- |
| **0–10 seconds** | Demo header and **Stalled deal approval** selector. | “Business signals can become disconnected recommendations and unaudited actions. This fictional local demo shows one controlled stalled-deal path.” |
| **10–25 seconds** | **Workflow summary**, then Signal and Context timeline cards. | “Eight days without a reply creates a structured stalled-deal signal. MAWI assembles typed context for the fictional proposal and records stage evidence.” |
| **25–42 seconds** | Strategy and Action timeline cards, then proposed subject/body. | “Deterministic mode selects a strategy and drafts a follow-up. The action is proposed, not sent.” |
| **42–57 seconds** | **Approval required** panel; click **Approve & simulate execution** near second 52. | “The workflow pauses at human review. The reviewer can edit, reject, or explicitly approve; approval behavior is preserved.” |
| **57–70 seconds** | **Outcome** simulated email/CRM cards and tool events. | “Approval resumes simulated execution. These receipts and tool events are local evidence—not real email or CRM activity.” |
| **70–82 seconds** | Outcome label, evaluator insight, recommended adjustment, and Memory timeline card. | “The evaluator records the simulated outcome and writes an insight for future persona-level retrieval. No business outcome is claimed.” |
| **82–90 seconds** | Prepared Profile B telemetry and Signal fallback marker. | “Here, an optional LLM configuration failure is recorded. MAWI falls back deterministically and still stops at approval, without making a provider request.” |

## Recording safety checklist

- Use fictional data only. The canonical fixtures already label accounts and people as fictional/example records.
- Hide tokens and environment values. Enter the bearer token before recording and keep its password field outside every crop.
- Label all email and CRM actions as **simulated** in captions and narration.
- Do not claim measured business outcomes, benchmarks, conversion changes, revenue impact, or production readiness.
- Do not show raw internal credentials, `.env`, shell history containing secrets, request authorization headers, or browser storage.
- Do not describe planned workflows as implemented. Limit narration to the `deal_followup_workflow` evidence visible in this guide.
- Do not call the controlled missing-key result a provider outage or invalid-JSON response; it demonstrates a local configuration failure and deterministic fallback.
- Keep deterministic mode as the canonical default. Profile B is a short, isolated proof state and must be restored to disabled afterward.

## Intentionally outside this phase

This workflow does not capture screenshots, record video, launch browser automation, connect external systems, modify production data, add workflows, or claim outcomes. No capture helper is needed because the existing demo reset, scenario selector, approval control, and two explicit environment profiles make every required state reproducible.
