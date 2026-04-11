"""
Purpose:
Orchestrator module `retry_policy` for coordinating workflow execution mechanics.

Technical Details:
Handles sequencing, retries, and auditability while delegating domain decisions to dedicated agents and tools.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def with_retries(
    fn: Callable[[], T],
    retries: int = 2,
    *,
    backoff_seconds: float | None = None,
    terminal_error_classes: tuple[type[Exception], ...] | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    last_error: Exception | None = None
    terminal_types = terminal_error_classes or ()
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if terminal_types and isinstance(exc, terminal_types):
                setattr(exc, "terminal_retry_error", True)
                raise
            last_error = exc
            if attempt >= retries:
                break
            delay = (backoff_seconds or 0.0) * (2**attempt) if backoff_seconds else 0.0
            if on_retry:
                on_retry(attempt + 1, exc, delay)
            if delay > 0:
                time.sleep(delay)
    assert last_error is not None
    raise last_error
