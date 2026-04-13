"""Runtime configuration helpers for optional LLM-driven agent behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_LLM_TIMEOUT_SEC = 30.0
DEFAULT_LLM_MAX_RETRIES = 2


@dataclass(frozen=True)
class RuntimeLLMConfig:
    enabled: bool = False
    provider: str = DEFAULT_LLM_PROVIDER
    openai_model: str = DEFAULT_OPENAI_MODEL
    timeout_sec: float = DEFAULT_LLM_TIMEOUT_SEC
    max_retries: int = DEFAULT_LLM_MAX_RETRIES


def load_runtime_llm_config() -> RuntimeLLMConfig:
    return RuntimeLLMConfig(
        enabled=_bool_env("MAWI_LLM_ENABLED", default=False),
        provider=os.getenv("MAWI_LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower() or DEFAULT_LLM_PROVIDER,
        openai_model=(
            os.getenv("MAWI_OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
            or DEFAULT_OPENAI_MODEL
        ),
        timeout_sec=_float_env("MAWI_LLM_TIMEOUT_SEC", DEFAULT_LLM_TIMEOUT_SEC),
        max_retries=_int_env("MAWI_LLM_MAX_RETRIES", DEFAULT_LLM_MAX_RETRIES),
    )


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
