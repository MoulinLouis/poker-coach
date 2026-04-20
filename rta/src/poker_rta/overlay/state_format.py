"""Pure-data helpers for the state mirror panel.

Split from `state_panel.py` so tests can assert on format/classification
logic without importing PyQt6 (headless CI lacks libGL).
"""

from __future__ import annotations

from typing import Any


def format_bb(chips: int | float, bb: int | float) -> float:
    """Convert chips → BB, rounded to 1 decimal. Returns 0.0 when bb<=0
    so the UI never shows NaN or raises."""
    if bb <= 0:
        return 0.0
    return round(float(chips) / float(bb), 1)


def classify_to_act(state: dict[str, Any] | None) -> str | None:
    """Return the seat that should act next, or None for no-state /
    unrecognized values. Keeps the paint logic from drawing a
    highlight for a garbage `to_act` string."""
    if state is None:
        return None
    value = state.get("to_act")
    if value == "hero" or value == "villain":
        return str(value)
    return None


def rendered_cards_from_state(state: dict[str, Any] | None) -> tuple[str, ...]:
    """Hero hole cards + board cards in one flat tuple. Empty when no state."""
    if state is None:
        return ()
    hero = tuple(state.get("hero_hole") or ())
    board = tuple(state.get("board") or ())
    return tuple(str(c) for c in hero) + tuple(str(c) for c in board)
