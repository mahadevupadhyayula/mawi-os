"""Provider-agnostic LLM JSON generation with an OpenAI-backed implementation."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    required_fields: list[str]
    model: str
    temperature: float = 0.0
    timeout_sec: float = 30.0
    max_retries: int | None = None
    retry_backoff_sec: float | None = None


@dataclass(frozen=True)
class LLMResult:
    raw_text: str
    payload: dict[str, Any] | None
    latency_ms: int
    provider: str
    model: str
    error: str | None
    token_usage: dict[str, int] | None
    redaction_occurred: bool | None = None


def generate_json(request: LLMRequest) -> LLMResult:
    """Generate JSON from a prompt, validating required fields and returning structured errors.

    Error codes:
    * provider_error
    * timeout
    * invalid_json
    * missing_required_fields
    """

    provider = os.getenv("MAWI_LLM_PROVIDER", "openai").strip().lower()
    if provider != "openai":
        return _result(
            raw_text=f"Unsupported provider: {provider}",
            payload=None,
            started_at=time.perf_counter(),
            provider=provider,
            model=request.model,
            error="provider_error",
            token_usage=None,
            redaction_occurred=None,
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _result(
            raw_text="Missing OPENAI_API_KEY",
            payload=None,
            started_at=time.perf_counter(),
            provider=provider,
            model=request.model,
            error="provider_error",
            token_usage=None,
            redaction_occurred=None,
        )

    model = (
        os.getenv("MAWI_OPENAI_MODEL", "").strip()
        or os.getenv("MAWI_LLM_MODEL", "").strip()
        or request.model
    )
    temperature = _float_env("MAWI_LLM_TEMPERATURE", request.temperature)
    timeout_sec = _float_env("MAWI_LLM_TIMEOUT_SEC", request.timeout_sec)
    max_retries = request.max_retries
    if max_retries is None:
        max_retries = _int_env("MAWI_LLM_MAX_RETRIES", 2)
    backoff_sec = request.retry_backoff_sec
    if backoff_sec is None:
        backoff_sec = _float_env("MAWI_LLM_RETRY_BACKOFF_SEC", 0.6)
    base_url = os.getenv("MAWI_LLM_BASE_URL", "https://api.openai.com").rstrip("/")

    started_at = time.perf_counter()
    last_raw_text = ""
    last_error_code: str = "provider_error"
    redaction_enabled = _bool_env("MAWI_LLM_REDACTION_ENABLED", default=True)
    redact_names = _bool_env("MAWI_LLM_REDACT_NAMES", default=False)
    outbound_prompt, redaction_occurred = redact_prompt_text(
        request.prompt,
        redact_names=redact_names,
        enabled=redaction_enabled,
    )

    for attempt in range(max_retries + 1):
        try:
            response_json = _call_openai_chat_completions(
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=temperature,
                prompt=outbound_prompt,
                required_fields=request.required_fields,
                timeout_sec=timeout_sec,
            )
            raw_text = _extract_content(response_json)
            last_raw_text = raw_text

            payload = _parse_json_payload(raw_text)
            if payload is None:
                last_error_code = "invalid_json"
                if attempt < max_retries:
                    _sleep_before_retry(backoff_sec, attempt)
                    continue
                return _result(last_raw_text, None, started_at, provider, model, "invalid_json", None, redaction_occurred)

            missing_fields = [field for field in request.required_fields if field not in payload]
            if missing_fields:
                return _result(
                    raw_text=raw_text,
                    payload=payload,
                    started_at=started_at,
                    provider=provider,
                    model=model,
                    error="missing_required_fields",
                    token_usage=_extract_token_usage(response_json),
                    redaction_occurred=redaction_occurred,
                )

            return _result(
                raw_text,
                payload,
                started_at,
                provider,
                model,
                None,
                _extract_token_usage(response_json),
                redaction_occurred,
            )

        except TimeoutError as exc:
            last_raw_text = str(exc)
            last_error_code = "timeout"
            if attempt < max_retries:
                _sleep_before_retry(backoff_sec, attempt)
                continue
            return _result(last_raw_text, None, started_at, provider, model, "timeout", None, redaction_occurred)

        except _RetryableProviderError as exc:
            last_raw_text = str(exc)
            last_error_code = "provider_error"
            if attempt < max_retries:
                _sleep_before_retry(backoff_sec, attempt)
                continue
            return _result(last_raw_text, None, started_at, provider, model, "provider_error", None, redaction_occurred)

        except Exception as exc:  # Defensive catch to ensure structured errors.
            return _result(str(exc), None, started_at, provider, model, "provider_error", None, redaction_occurred)

    return _result(last_raw_text, None, started_at, provider, model, last_error_code, None, redaction_occurred)


_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_LONG_NUMERIC_ID_PATTERN = re.compile(r"\b\d{8,}\b")
_PHONE_TOKEN_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{7,}\d)(?!\w)")
_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]{1,})(?:\s+([A-Z][a-z]{1,}))+")


def redact_prompt_text(prompt: str, *, redact_names: bool = False, enabled: bool = True) -> tuple[str, bool]:
    if not enabled or not prompt:
        return prompt, False
    redacted = prompt
    redacted = _EMAIL_PATTERN.sub("<redacted_email>", redacted)
    redacted = _LONG_NUMERIC_ID_PATTERN.sub("<redacted_numeric_id>", redacted)
    redacted = _PHONE_TOKEN_PATTERN.sub("<redacted_phone>", redacted)
    if redact_names:
        redacted = _NAME_PATTERN.sub("<redacted_name>", redacted)
    return redacted, redacted != prompt


class _RetryableProviderError(Exception):
    pass


def _call_openai_chat_completions(
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    prompt: str,
    required_fields: list[str],
    timeout_sec: float,
) -> dict[str, Any]:
    url = f"{base_url}/v1/chat/completions"
    required_fields_str = ", ".join(required_fields) if required_fields else "none"
    body = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You must output valid JSON only. "
                    f"The response must include these fields: {required_fields_str}."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    encoded = json.dumps(body).encode("utf-8")
    req = urllib_request.Request(
        url=url,
        data=encoded,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=timeout_sec) as resp:
            response_text = resp.read().decode("utf-8")
            return json.loads(response_text)
    except urllib_error.HTTPError as exc:
        status = exc.code
        details = exc.read().decode("utf-8", errors="replace")
        if status in (408, 409, 429) or status >= 500:
            raise _RetryableProviderError(f"HTTP {status}: {details}") from exc
        raise RuntimeError(f"HTTP {status}: {details}") from exc
    except urllib_error.URLError as exc:
        message = str(exc.reason)
        if "timed out" in message.lower():
            raise TimeoutError(message) from exc
        raise _RetryableProviderError(message) from exc


def _extract_content(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Provider returned no choices")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
        return "\n".join(text_parts).strip()
    return str(content).strip()


def _parse_json_payload(raw_text: str) -> dict[str, Any] | None:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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


def _sleep_before_retry(backoff_sec: float, attempt: int) -> None:
    time.sleep(max(0.0, backoff_sec) * (2**attempt))


def _result(
    raw_text: str,
    payload: dict[str, Any] | None,
    started_at: float,
    provider: str,
    model: str,
    error: str | None,
    token_usage: dict[str, int] | None,
    redaction_occurred: bool | None,
) -> LLMResult:
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return LLMResult(
        raw_text=raw_text,
        payload=payload,
        latency_ms=latency_ms,
        provider=provider,
        model=model,
        error=error,
        token_usage=token_usage,
        redaction_occurred=redaction_occurred,
    )


def _extract_token_usage(response_json: dict[str, Any]) -> dict[str, int] | None:
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return None
    normalized: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            normalized[key] = value
    return normalized or None


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
