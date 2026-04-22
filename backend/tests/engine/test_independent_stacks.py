"""Independent hero/villain starting stacks.

The engine historically assumed both seats started equal. Tournament
play (especially late-SnG HU) almost never has equal stacks, so the
signature accepts hero_stack + villain_stack. Legacy callers can still
pass effective_stack for equal stacks — the helper maps that to
hero_stack=villain_stack.
"""

from __future__ import annotations

import pytest

from poker_coach.engine.rules import start_hand


def test_unequal_stacks_button_short() -> None:
    state = start_hand(
        hero_stack=1_600,
        villain_stack=2_400,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    assert state.hero_stack_start == 1_600
    assert state.villain_stack_start == 2_400
    # effective = min(hero, villain) = 1600
    assert state.effective_stack == 1_600
    # Stacks behind after blinds (button=hero posts SB=50; villain posts BB=100):
    assert state.stacks == {"hero": 1_550, "villain": 2_300}


def test_unequal_stacks_bb_short() -> None:
    state = start_hand(
        hero_stack=3_000,
        villain_stack=800,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    assert state.effective_stack == 800
    assert state.stacks == {"hero": 2_950, "villain": 700}


def test_effective_stack_legacy_signature_still_works() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    assert state.hero_stack_start == 10_000
    assert state.villain_stack_start == 10_000
    assert state.effective_stack == 10_000


def test_must_provide_either_effective_or_both_stacks() -> None:
    with pytest.raises(ValueError, match="effective_stack"):
        start_hand(
            hero_stack=1_000,  # villain_stack missing
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
        )


def test_cannot_provide_both_shapes() -> None:
    with pytest.raises(ValueError, match="either"):
        start_hand(
            effective_stack=1_000,
            hero_stack=1_000,
            villain_stack=1_000,
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
        )


def test_ante_with_asymmetric_stacks_preserves_chip_conservation() -> None:
    """Ante + independent stacks: posting should subtract exactly the right
    amounts from each seat and add them to the pot.

    Setup: hero stack 5000, villain stack 8000, bb=100, ante=100, button=hero.
    → hero (SB) posts 50 SB = 50. hero stack after = 4950.
    → villain (BB) posts 100 BB + 100 ante = 200. villain stack after = 7800.
    → committed: hero=50, villain=100. pot = 100 (ante only; blinds are live).
    Total chips = 4950 + 7800 + 50 + 100 + 100 = 13000 = 5000 + 8000.
    """
    state = start_hand(
        hero_stack=5000,
        villain_stack=8000,
        bb=100,
        ante=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    total = sum(state.stacks.values()) + state.pot + sum(state.committed.values())
    assert total == 13_000, (
        f"chip conservation broken: stacks={state.stacks} pot={state.pot} "
        f"committed={state.committed} total={total}"
    )
    # Specific amounts per seat:
    assert state.stacks["hero"] == 4_950, (
        f"hero posted 50 SB, stack should be 4950, got {state.stacks['hero']}"
    )
    assert state.stacks["villain"] == 7_800, (
        f"villain posted 100 BB + 100 ante, stack should be 7800, got {state.stacks['villain']}"
    )
