"""Tests for BB-ante handling.

Format modeled: the BB seat posts a single ante of size `ante` on top
of the big blind. The ante goes straight into `pot` as dead money.
Blinds remain in `committed` as live bets (unchanged by ante).
"""

from __future__ import annotations

import pytest

from poker_coach.engine.rules import start_hand


def test_start_hand_with_zero_ante_matches_pre_ante_behavior() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        ante=0,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    assert state.ante == 0
    assert state.pot == 0
    assert state.stacks == {"hero": 9_950, "villain": 9_900}


def test_start_hand_with_bb_ante_posts_to_pot_from_bb_stack() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        ante=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    # BB (villain) pays both the blind AND the ante.
    assert state.ante == 100
    assert state.pot == 100  # ante as dead money
    assert state.stacks["hero"] == 9_950  # only SB deducted
    assert state.stacks["villain"] == 10_000 - 100 - 100  # BB + ante
    # Live bets unchanged by ante:
    assert state.committed == {"hero": 50, "villain": 100}


def test_negative_ante_rejected() -> None:
    with pytest.raises(ValueError, match="ante"):
        start_hand(
            effective_stack=10_000,
            bb=100,
            ante=-5,
            button="hero",
            hero_hole=("As", "Kd"),
            villain_hole=("Qc", "Qh"),
        )


def test_ante_exceeds_bb_stack_rejected() -> None:
    # BB doesn't have enough for BB + ante → illegal starting condition.
    with pytest.raises(ValueError):
        start_hand(
            effective_stack=150,
            bb=100,
            ante=100,
            button="hero",
            hero_hole=("As", "Kd"),
            villain_hole=("Qc", "Qh"),
        )
