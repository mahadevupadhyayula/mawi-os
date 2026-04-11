from __future__ import annotations

from typing import Callable, TypeVar


T = TypeVar("T")


def with_retries(fn: Callable[[], T], retries: int = 2) -> T:
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    assert last_error is not None
    raise last_error
