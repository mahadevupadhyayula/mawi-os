from __future__ import annotations


def requires_approval(confidence: float, threshold: float) -> bool:
    return confidence < threshold
