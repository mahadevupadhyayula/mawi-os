"""Shared LLM inference block utilities for agent model-output assembly."""

from __future__ import annotations

import json
import logging

from agents.llm_client import LLMRequest, generate_json
from agents.prompt_templates import validate_model_output_json


def resolve_model_output(
    *,
    llm_enabled: bool,
    deterministic_json_string: str,
    prompt_text: str,
    required_fields: list[str],
    stage_name: str,
    model: str,
    timeout_sec: float,
    logger: logging.Logger,
) -> str:
    if llm_enabled:
        llm_result = generate_json(
            LLMRequest(
                prompt=prompt_text,
                required_fields=required_fields,
                model=model,
                timeout_sec=timeout_sec,
            )
        )
        if llm_result.error:
            logger.warning("%s llm fallback: %s", stage_name, llm_result.error)
        elif llm_result.payload is None:
            logger.warning("%s llm fallback: empty payload", stage_name)
        else:
            llm_validation = validate_model_output_json(
                model_output=json.dumps(llm_result.payload),
                required_json_fields=required_fields,
                stage_name=stage_name,
            )
            if llm_validation["ok"]:
                return json.dumps(llm_result.payload)
            logger.warning("%s llm validation fallback: %s", stage_name, llm_validation["errors"])

    return deterministic_json_string
