"""Evaluation metrics: per-component CV accuracy and end-to-end state
reconstruction accuracy. Used in the paper and as a regression guard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CVAccuracy:
    correct: int
    total: int
    rate: float


def evaluate_card_accuracy(got: list[tuple[str, str]], gold: list[tuple[str, str]]) -> CVAccuracy:
    correct = sum((g[0] == h[0]) + (g[1] == h[1]) for g, h in zip(got, gold, strict=True))
    total = len(got) * 2
    return CVAccuracy(correct=correct, total=total, rate=correct / total if total else 0.0)
