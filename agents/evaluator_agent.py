"""
Purpose:
Agent module `evaluator_agent` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

import json
import logging

from agents.contracts import ExecutionOutcome, make_result
from agents.inference import resolve_model_output
from agents.prompt_templates import (
    PromptLintError,
    attach_prompt_run_metadata,
    render_prompt,
    required_json_fields,
    validate_model_output_json,
)
from agents.runtime_config import load_runtime_llm_config
from context.models import ExecutionContext, OutcomeContext
from evaluation.outcome_analyzer import classify_outcome_detailed

LOGGER = logging.getLogger(__name__)


def evaluator_agent(
    execution_context: ExecutionContext,
    outcome: ExecutionOutcome,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> OutcomeContext:
    prompt_text = render_prompt(
        "evaluator_prompt.txt",
        prompt_contract={
            "workflow_goal": "Evaluate execution outcomes and produce reusable learning signals.",
            "stage_name": "evaluator_agent",
            "policy_mode": "observe_only",
            "output_model": OutcomeContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "evaluator_agent",
        },
    )
    outcome_label = classify_outcome_detailed(outcome, execution_success=execution_context.status == "executed")
    if outcome_label == "delivery_failure":
        label = "negative"
        insight = "Execution reliability issues reduced follow-up quality."
        adjustment = "Improve tool retry and fallback policies."
        confidence = 0.7
    elif outcome_label == "positive":
        label = "positive"
        insight = "ROI framing improved reply likelihood for this persona."
        adjustment = "Prioritize ROI framing for similar stalled proposal-stage deals."
        confidence = 0.85
    elif outcome_label == "delayed_positive":
        label = "positive"
        insight = "Late interest signal observed; sequencing likely worked with slower buyer timing."
        adjustment = "Retain sequence structure and extend follow-up window before switching tactics."
        confidence = 0.74
    else:
        label = "neutral"
        insight = "Action executed but no reply yet; timing or message angle may need refinement."
        adjustment = "Test shorter CTA and add concrete next-step options."
        confidence = 0.65

    reasoning = "Compared execution result with observed outcome and generated learning signal."
    deterministic_payload = {
        "outcome_label": label,
        "insight": insight,
        "recommended_adjustment": adjustment,
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(OutcomeContext)
    deterministic_json_string = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    llm_enabled = runtime_config.enabled
    resolution = resolve_model_output(
        llm_enabled=llm_enabled,
        deterministic_json_string=deterministic_json_string,
        prompt_text=prompt_text,
        required_fields=required_fields,
        stage_name="evaluator_agent",
        model=runtime_config.openai_model,
        timeout_sec=runtime_config.timeout_sec,
        max_retries=runtime_config.max_retries,
        logger=LOGGER,
    )
    attach_prompt_run_metadata(
        run_id=str(run_id or "adhoc-run"),
        agent_id="evaluator_agent",
        prompt_name="evaluator_prompt.txt",
        llm_enabled=resolution.llm_enabled,
        provider=resolution.provider,
        model=resolution.model,
        llm_latency_ms=resolution.llm_latency_ms,
        token_usage=resolution.token_usage,
        fallback_reason=resolution.fallback_reason,
    )
    validation = validate_model_output_json(
        model_output=resolution.model_output,
        required_json_fields=required_fields,
        stage_name="evaluator_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"evaluator_agent output failed validation: {validation['errors']}")
    payload = validation["payload"]
    assert isinstance(payload, dict)
    final_reasoning = str(payload["reasoning"])
    final_confidence = float(payload["confidence"])
    result = make_result(
        OutcomeContext(
            outcome_label=str(payload["outcome_label"]),
            insight=str(payload["insight"]),
            recommended_adjustment=str(payload["recommended_adjustment"]),
            reasoning=final_reasoning,
            confidence=final_confidence,
        ),
        final_reasoning,
        final_confidence,
    )
    return result.payload
