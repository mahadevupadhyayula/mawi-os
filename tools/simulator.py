from __future__ import annotations

from random import random


def simulate_success(probability: float = 0.95) -> bool:
    return random() < probability
