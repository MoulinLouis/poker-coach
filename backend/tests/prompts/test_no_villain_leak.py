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

from pathlib import Path

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


def test_coach_variables_omit_forbidden_keys() -> None:
    state = _sample_state(("As", "Kd"), ("Qc", "Qh"))
    variables = state_to_coach_variables(state)
    leaked = FORBIDDEN_KEYS & set(variables.keys())
    assert leaked == set(), f"leaked keys: {leaked}"


def test_coach_v1_declared_vars_omit_forbidden_keys() -> None:
    renderer = PromptRenderer(PROMPTS_ROOT)
    template = renderer.load("coach", "v1")
    declared = set(template.declared_variables)
    leaked = FORBIDDEN_KEYS & declared
    assert leaked == set(), f"coach/v1 declares forbidden variables: {leaked}"


def test_rendered_coach_prompt_does_not_contain_villain_cards() -> None:
    # Use cards that are trivially distinguishable in text.
    hero = ("2c", "3c")
    villain = ("7h", "7s")
    state = _sample_state(hero, villain)

    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render("coach", "v1", state_to_coach_variables(state))

    assert "7h" not in rendered.rendered_prompt
    assert "7s" not in rendered.rendered_prompt
    # Hero cards should be there.
    assert "2c" in rendered.rendered_prompt
    assert "3c" in rendered.rendered_prompt


def test_rendered_prompt_also_excludes_deck_snapshot(tmp_path: Path) -> None:
    # Even with a seeded deck, deck cards that are not yet on the board
    # (including villain's hole cards) must not appear in the prompt.
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        rng_seed=42,
    )
    assert state.deck_snapshot is not None

    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render("coach", "v1", state_to_coach_variables(state))

    # Cards dealt to villain (deck indices 2, 3) must not leak.
    villain_0, villain_1 = state.deck_snapshot[2], state.deck_snapshot[3]
    assert villain_0 not in rendered.rendered_prompt
    assert villain_1 not in rendered.rendered_prompt
    # Undealt flop/turn/river (indices 4-8) must not leak either.
    for unexposed in state.deck_snapshot[4:9]:
        assert unexposed not in rendered.rendered_prompt, (
            f"unexposed board card {unexposed} leaked into prompt"
        )
