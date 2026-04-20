from __future__ import annotations

import math

from poker_rta.detection.timing import decision_time_entropy


def test_uniform_decisions_have_high_entropy() -> None:
    times_ms = list(range(500, 30000, 200))
    e = decision_time_entropy(times_ms, bins=16)
    assert e > 3.0


def test_bot_like_narrow_timing_has_low_entropy() -> None:
    times_ms = [1500] * 50 + [1550] * 50
    e = decision_time_entropy(times_ms, bins=16)
    assert e < 1.5
    assert not math.isnan(e)
