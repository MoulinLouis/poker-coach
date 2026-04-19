"""Behavioral detection: timing-entropy of the player's decisions.

A key RTA tell is suspiciously consistent response latency — read the overlay,
click, repeat. Human players have wide natural variance. This module exposes
entropy and chi-square distance-from-human-prior metrics the paper cites.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


def decision_time_entropy(times_ms: Iterable[int], bins: int = 16) -> float:
    times = list(times_ms)
    if not times:
        return 0.0
    lo, hi = min(times), max(times)
    width = max(1, (hi - lo) / bins)
    buckets = Counter(min(bins - 1, int((t - lo) / width)) for t in times)
    total = sum(buckets.values())
    return -sum((n / total) * math.log2(n / total) for n in buckets.values())
