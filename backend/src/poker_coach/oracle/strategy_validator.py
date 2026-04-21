"""Validate and normalize a raw mixed-strategy list from an LLM tool call.

The LLM returns `strategy` as a list of dicts. This module:

- enforces that every action is in the spot's legal_actions;
- enforces sizing presence/absence and range for bet/raise;
- merges duplicate (action, to_amount_bb) entries by summing their frequencies;
- drops entries with frequency == 0;
- normalizes frequency sums within a 0.98..1.02 tolerance band to exactly 1.0;
- rejects sums outside that band, or an empty result after cleanup.

The output is sorted descending by frequency so the argmax is always first.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from poker_coach.engine.models import ActionType, LegalAction
from poker_coach.oracle.base import StrategyEntry

_SIZING_ACTIONS = {"bet", "raise"}
_NON_SIZING_ACTIONS = {"fold", "check", "call", "allin"}
_TOLERANCE_LOW = 0.98
_TOLERANCE_HIGH = 1.02

_ACTION_CONSERVATISM: dict[str, int] = {
    "fold": 0,
    "check": 1,
    "call": 2,
    "bet": 3,
    "raise": 4,
    "allin": 5,
}


def normalize_strategy(
    raw: list[dict[str, Any]],
    legal_actions: list[LegalAction],
    bb_chips: int,
) -> list[StrategyEntry]:
    """Validate and normalize raw strategy entries from an LLM tool call.

    `legal_actions` uses integer chips for min_to/max_to; `bb_chips` is the
    number of chips per big blind so we can compare the LLM's BB-denominated
    sizing to the legal range.
    """
    by_legal_type = {la.type: la for la in legal_actions}

    validated: list[tuple[str, float | None, float]] = []
    for i, entry in enumerate(raw):
        try:
            action = entry["action"]
            to_amount_bb = entry["to_amount_bb"]
            frequency = float(entry["frequency"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"strategy entry {i} malformed: {exc}") from exc

        if action not in by_legal_type:
            raise ValueError(f"action {action!r} not legal in this spot")

        la = by_legal_type[action]

        if action in _SIZING_ACTIONS:
            if to_amount_bb is None:
                raise ValueError(f"sizing required for action {action!r}")
            to_chips = round(to_amount_bb * bb_chips)
            if la.min_to is not None and to_chips < la.min_to:
                raise ValueError(
                    f"sizing {to_amount_bb}bb out of range for {action!r}"
                )
            if la.max_to is not None and to_chips > la.max_to:
                raise ValueError(
                    f"sizing {to_amount_bb}bb out of range for {action!r}"
                )
        elif action in _NON_SIZING_ACTIONS:
            if to_amount_bb is not None:
                raise ValueError(
                    f"to_amount_bb must be null for action {action!r}"
                )
        else:
            raise ValueError(f"unknown action {action!r}")

        if frequency < 0:
            raise ValueError(f"negative frequency in entry {i}")

        validated.append((action, to_amount_bb, frequency))

    merged: dict[tuple[str, float | None], float] = defaultdict(float)
    for action, to_amount_bb, frequency in validated:
        merged[(action, to_amount_bb)] += frequency

    merged = {k: v for k, v in merged.items() if v > 0}
    if not merged:
        raise ValueError("strategy is empty after dropping zero-frequency entries")

    total = sum(merged.values())
    if total < _TOLERANCE_LOW or total > _TOLERANCE_HIGH:
        raise ValueError(
            f"frequencies sum to {total:.4f}, outside tolerance "
            f"[{_TOLERANCE_LOW}, {_TOLERANCE_HIGH}]"
        )

    scale = 1.0 / total
    entries: list[StrategyEntry] = []
    for (action_key, to_amount_bb_key), freq in merged.items():
        action_typed: ActionType = action_key  # type: ignore[assignment]
        entries.append(
            StrategyEntry(
                action=action_typed,
                to_amount_bb=to_amount_bb_key,
                frequency=freq * scale,
            )
        )

    entries.sort(
        key=lambda e: (
            -e.frequency,
            _ACTION_CONSERVATISM[e.action],
            e.to_amount_bb if e.to_amount_bb is not None else 0.0,
        )
    )
    return entries


__all__ = ["normalize_strategy"]
