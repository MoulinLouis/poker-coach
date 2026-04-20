"""Coach v2 rendering — stack-depth bucket + SPR surfacing.

Anchors that the prompt exposes the effective-stack regime the LLM is
actually in, so the model doesn't have to re-derive `shallow` at 47bb
every call. The bucket boundaries (<50 shallow, >150 deep, else
standard) are cited directly in the system prompt; drift here decouples
the two.
"""

from __future__ import annotations

import pytest

from poker_coach.analytics import VillainStats
from poker_coach.engine.rules import start_hand
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer
from poker_coach.settings import PROMPTS_ROOT


@pytest.mark.parametrize(
    ("effective_stack", "expected_bucket"),
    [
        (3_000, "shallow"),
        (10_000, "standard"),
        (20_000, "deep"),
    ],
)
def test_stack_depth_bucket_classifies_regime(
    effective_stack: int,
    expected_bucket: str,
) -> None:
    state = start_hand(
        effective_stack=effective_stack,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    variables = state_to_coach_variables(state, villain_profile="unknown")
    assert variables["stack_depth_bucket"] == expected_bucket


def test_stack_depth_bucket_boundaries_are_inclusive_of_standard() -> None:
    """50bb and 150bb are both inside the standard band."""
    for effective_stack in (5_000, 15_000):
        state = start_hand(
            effective_stack=effective_stack,
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
            villain_hole=("Qc", "Qh"),
        )
        variables = state_to_coach_variables(state, villain_profile="unknown")
        assert variables["stack_depth_bucket"] == "standard"


def test_spr_bb_guards_empty_pot_divide_by_zero() -> None:
    """At hand start the pot is 0 (blinds live in `committed`). The
    guard (`max(pot_bb, 0.5)`) keeps SPR finite rather than infinite."""
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    variables = state_to_coach_variables(state, villain_profile="unknown")
    assert variables["pot_bb"] == 0.0
    # Effective 100bb / max(0, 0.5) = 200. Finite, not NaN, not Inf.
    assert variables["spr_bb"] == pytest.approx(200.0)


@pytest.mark.parametrize(
    ("effective_stack", "token"),
    [
        (3_000, "shallow"),
        (10_000, "standard"),
        (20_000, "deep"),
    ],
)
def test_coach_v2_renders_bucket_token(effective_stack: int, token: str) -> None:
    state = start_hand(
        effective_stack=effective_stack,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    renderer = PromptRenderer(PROMPTS_ROOT)
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown",
        villain_stats=VillainStats.zero().as_prompt_payload(),
    )
    rendered = renderer.render("coach", "v2", variables)
    assert f"Stack depth: {token}" in rendered.rendered_prompt
    assert "SPR" in rendered.rendered_prompt
