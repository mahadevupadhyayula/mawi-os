from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def with_retry(fn: Callable[[], T], retries: int = 2, backoff_sec: float = 0.1) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(backoff_sec * attempt)
