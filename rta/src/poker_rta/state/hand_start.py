from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from poker_rta.cv.pipeline import FrameObservation

Seat = Literal["hero", "villain"]


@dataclass(frozen=True)
class HandStartParams:
    effective_stack: int
    bb: int
    button: Seat
    hero_hole: tuple[str, str]


def detect_hand_start(
    *,
    prev: FrameObservation | None,
    current: FrameObservation,
    bb: int,
) -> HandStartParams | None:
    if current.hero_cards is None or current.board:
        return None
    if prev is not None and prev.hero_cards == current.hero_cards and not prev.board:
        return None
    sb = bb // 2
    hero_bet = current.hero_bet_chips or 0
    villain_bet = current.villain_bet_chips or 0
    if {hero_bet, villain_bet} != {sb, bb}:
        return None
    button: Seat = "hero" if hero_bet == sb else "villain"
    hero_stack = current.hero_stack_chips or 0
    villain_stack = current.villain_stack_chips or 0
    effective = min(hero_stack + hero_bet, villain_stack + villain_bet)
    return HandStartParams(effective, bb, button, current.hero_cards)
