"""Convergence score between the player's actual actions and a GTO baseline.

RTA users tend to converge on a single oracle's recommendations across many
spots — detectable as higher-than-population agreement with any given baseline.
Hand-by-hand agreement rate is noisy; aggregate over N >= 200 decisions.
"""

from __future__ import annotations

from collections.abc import Sequence


def convergence_score(played: Sequence[str], baseline: Sequence[str]) -> float:
    if len(played) != len(baseline):
        raise ValueError("played and baseline must be the same length")
    if not played:
        return 0.0
    return sum(1 for a, b in zip(played, baseline, strict=True) if a == b) / len(played)
