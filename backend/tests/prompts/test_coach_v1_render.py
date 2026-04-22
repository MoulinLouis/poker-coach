"""Render tests for prompts/coach/v1.md.

v1 is the legacy single-verdict prompt. It was edited in f7a306f to include
pot_bb_live — pin that here so it doesn't silently regress.
"""

from __future__ import annotations

import pytest

from poker_coach.engine.models import Action
from poker_coach.engine.rules import apply_action, start_hand
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer
from poker_coach.settings import PROMPTS_ROOT


def test_v1_renders_pot_bb_live() -> None:
    state = start_hand(effective_stack=10_000, bb=100, button="hero", hero_hole=("As", "Kd"))
    # Hero opens to 250, villain raises to 900 → live pot = 1150 chips = 11.5 bb.
    state = apply_action(state, Action(actor="hero", type="raise", to_amount=250))
    state = apply_action(state, Action(actor="villain", type="raise", to_amount=900))

    # v1 doesn't declare villain_profile / villain_stats — omit them here.
    variables = state_to_coach_variables(state)
    assert variables["pot_bb_live"] == pytest.approx(11.5)

    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render("coach", "v1", variables)
    assert "Pot (live, including this street): 11.5 bb" in rendered.rendered_prompt
