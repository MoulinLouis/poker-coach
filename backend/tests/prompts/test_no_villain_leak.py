"""Regression tests: villain information must never reach the LLM.

The LLM coach plays as hero with incomplete information — villain's hole
cards, the remaining deck, and the RNG seed are all *known* to the
backend (for replay and showdown) but must never appear in what the
oracle sees. These tests enforce that at three layers:

1. `state_to_coach_variables` never emits keys containing villain hole
   information, even when the field is set.
2. The coach prompt's declared variable list never contains villain
   hidden fields.
3. The fully rendered prompt string never contains the villain's hole
   cards (checked with a concrete state where villain holds easily
   grep-able cards).
"""

import pytest

from poker_coach.engine.rules import start_hand
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer
from poker_coach.settings import PROMPTS_ROOT

# Fields that MUST NOT reach the prompt.
FORBIDDEN_KEYS = {"villain_hole", "deck_snapshot", "rng_seed"}


def _sample_state(hero: tuple[str, str], villain: tuple[str, str]):
    return start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=hero,
        villain_hole=villain,
    )


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_coach_variables_omit_forbidden_keys(version: str) -> None:
    # Variables projection is version-agnostic, but both prompts must
    # consume the same projection shape modulo villain_profile.
    state = _sample_state(("As", "Kd"), ("Qc", "Qh"))
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    leaked = FORBIDDEN_KEYS & set(variables.keys())
    assert leaked == set(), f"leaked keys for {version}: {leaked}"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_coach_declared_vars_omit_forbidden_keys(version: str) -> None:
    renderer = PromptRenderer(PROMPTS_ROOT)
    template = renderer.load("coach", version)
    declared = set(template.declared_variables)
    leaked = FORBIDDEN_KEYS & declared
    assert leaked == set(), f"coach/{version} declares forbidden variables: {leaked}"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_rendered_coach_prompt_does_not_contain_villain_cards(version: str) -> None:
    hero = ("2c", "3c")
    villain = ("7h", "7s")
    state = _sample_state(hero, villain)

    renderer = PromptRenderer(PROMPTS_ROOT)
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    rendered = renderer.render("coach", version, variables)

    assert "7h" not in rendered.rendered_prompt
    assert "7s" not in rendered.rendered_prompt
    assert "2c" in rendered.rendered_prompt
    assert "3c" in rendered.rendered_prompt


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_rendered_prompt_also_excludes_deck_snapshot(version: str) -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        rng_seed=42,
    )
    assert state.deck_snapshot is not None

    renderer = PromptRenderer(PROMPTS_ROOT)
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    rendered = renderer.render("coach", version, variables)

    villain_0, villain_1 = state.deck_snapshot[2], state.deck_snapshot[3]
    assert villain_0 not in rendered.rendered_prompt
    assert villain_1 not in rendered.rendered_prompt
    for unexposed in state.deck_snapshot[4:9]:
        assert unexposed not in rendered.rendered_prompt, (
            f"unexposed board card {unexposed} leaked into {version} prompt"
        )
