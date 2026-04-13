"""
Purpose:
Implements the Signal Agent that interprets deal activity and identifies workflow-triggering events.

Technical Details:
Combines deterministic inactivity heuristics with typed SignalContext creation so downstream orchestration receives normalized event metadata.
"""

from __future__ import annotations

import json
import logging

from agents.contracts import make_result
from agents.llm_client import LLMRequest, generate_json
from agents.prompt_templates import PromptLintError, render_prompt, required_json_fields, validate_model_output_json
from agents.runtime_config import load_runtime_llm_config
from context.models import SignalContext

LOGGER = logging.getLogger(__name__)


def signal_agent(raw_data: dict, *, workflow_id: str = "deal_followup_workflow", run_id: str | None = None) -> SignalContext:
    prompt_text = render_prompt(
        "signal_prompt.txt",
        prompt_contract={
            "workflow_goal": "Detect stalled-deal triggers for follow-up workflows.",
            "stage_name": "signal_agent",
            "policy_mode": "observe_only",
            "output_model": SignalContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "signal_agent",
        },
    )
    days = int(raw_data.get("days_since_reply", 0))
    stalled = days >= 5
    urgency = "high" if days >= 10 else "medium" if stalled else "low"
    reasoning = f"Deal has no reply for {days} days."
    confidence = 0.9 if stalled else 0.7
    deterministic_payload = {
        "stalled": stalled,
        "days_since_reply": days,
        "urgency": urgency,
        "trigger_reason": "no_reply_5_days" if stalled else "not_stalled",
        "reasoning": reasoning,
        "confidence": confidence,
    }
    required_fields = required_json_fields(SignalContext)
    model_output = json.dumps(deterministic_payload)
    runtime_config = load_runtime_llm_config()
    if runtime_config.enabled:
        llm_result = generate_json(
            LLMRequest(
                prompt=prompt_text,
                required_fields=required_fields,
                model=runtime_config.openai_model,
                timeout_sec=runtime_config.timeout_sec,
            )
        )
        if llm_result.error:
            LOGGER.warning("signal_agent llm fallback: %s", llm_result.error)
        elif llm_result.payload is None:
            LOGGER.warning("signal_agent llm fallback: empty payload")
        else:
            llm_validation = validate_model_output_json(
                model_output=json.dumps(llm_result.payload),
                required_json_fields=required_fields,
                stage_name="signal_agent",
            )
            if llm_validation["ok"]:
                model_output = json.dumps(llm_result.payload)
            else:
                LOGGER.warning("signal_agent llm validation fallback: %s", llm_validation["errors"])
    validation = validate_model_output_json(
        model_output=model_output,
        required_json_fields=required_fields,
        stage_name="signal_agent",
    )
    if not validation["ok"]:
        raise PromptLintError(f"signal_agent output failed validation: {validation['errors']}")

    payload = validation["payload"]
    assert isinstance(payload, dict)
    result = make_result(
        SignalContext(
            stalled=bool(payload["stalled"]),
            days_since_reply=int(payload["days_since_reply"]),
            urgency=str(payload["urgency"]),
            trigger_reason=str(payload["trigger_reason"]),
            reasoning=str(payload["reasoning"]),
            confidence=float(payload["confidence"]),
        ),
        reasoning,
        confidence,
    )
    return result.payload
