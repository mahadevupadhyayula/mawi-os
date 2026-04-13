"""Shared LLM inference block utilities for agent model-output assembly."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from agents.llm_client import LLMRequest, generate_json
from agents.prompt_templates import validate_model_output_json


@dataclass(frozen=True)
class ModelResolution:
    model_output: str
    llm_enabled: bool
    provider: str | None = None
    model: str | None = None
    llm_latency_ms: int | None = None
    token_usage: dict[str, int] | None = None
    fallback_reason: str | None = None


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
) -> ModelResolution:
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
            return ModelResolution(
                model_output=deterministic_json_string,
                llm_enabled=True,
                provider=llm_result.provider,
                model=llm_result.model,
                llm_latency_ms=llm_result.latency_ms,
                token_usage=llm_result.token_usage,
                fallback_reason=f"llm_error:{llm_result.error}",
            )
        elif llm_result.payload is None:
            logger.warning("%s llm fallback: empty payload", stage_name)
            return ModelResolution(
                model_output=deterministic_json_string,
                llm_enabled=True,
                provider=llm_result.provider,
                model=llm_result.model,
                llm_latency_ms=llm_result.latency_ms,
                token_usage=llm_result.token_usage,
                fallback_reason="llm_empty_payload",
            )
        else:
            llm_validation = validate_model_output_json(
                model_output=json.dumps(llm_result.payload),
                required_json_fields=required_fields,
                stage_name=stage_name,
            )
            if llm_validation["ok"]:
                return ModelResolution(
                    model_output=json.dumps(llm_result.payload),
                    llm_enabled=True,
                    provider=llm_result.provider,
                    model=llm_result.model,
                    llm_latency_ms=llm_result.latency_ms,
                    token_usage=llm_result.token_usage,
                )
            logger.warning("%s llm validation fallback: %s", stage_name, llm_validation["errors"])
            return ModelResolution(
                model_output=deterministic_json_string,
                llm_enabled=True,
                provider=llm_result.provider,
                model=llm_result.model,
                llm_latency_ms=llm_result.latency_ms,
                token_usage=llm_result.token_usage,
                fallback_reason="llm_validation_failed",
            )

    return ModelResolution(model_output=deterministic_json_string, llm_enabled=False, fallback_reason="llm_disabled")
