from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from poker_rta.cv.pipeline import FrameObservation

_CRITICAL = ("hero_cards", "pot_chips", "hero_stack_chips", "villain_stack_chips")


@dataclass(frozen=True)
class GateDecision:
    fire: bool
    reason: str


def should_fire_decision(
    *,
    state: dict[str, Any],
    obs: FrameObservation,
    degraded: bool,
    already_fired_for_state_id: str | None,
    state_id: str,
    min_confidence: float,
) -> GateDecision:
    if degraded:
        return GateDecision(False, "session degraded")
    if state.get("to_act") != "hero":
        return GateDecision(False, f"to_act={state.get('to_act')!r}")
    for k in _CRITICAL:
        c = obs.confidence.get(k, 1.0)
        if c < min_confidence:
            return GateDecision(False, f"confidence {k}={c:.2f} < {min_confidence:.2f}")
    if already_fired_for_state_id == state_id:
        return GateDecision(False, "already fired")
    return GateDecision(True, "ok")
