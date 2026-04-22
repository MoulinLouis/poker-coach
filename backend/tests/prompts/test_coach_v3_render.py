from pathlib import Path

import pytest

from poker_coach.engine.models import Action
from poker_coach.engine.rules import apply_action, start_hand
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer
from poker_coach.settings import REPO_ROOT


def test_coach_v3_renders_with_v2_variables_plus_bb_chips() -> None:
    """v3 reuses the v2 variable set plus a `bb_chips` sidecar (not referenced
    in the template body; read by the backend validator)."""
    prompts_root = Path(__file__).resolve().parents[3] / "prompts"
    renderer = PromptRenderer(prompts_root)

    variables = {
        "street": "flop",
        "hero_hole": ["Ah", "Kh"],
        "board": ["2c", "7d", "Th"],
        "button": "hero",
        "pot_bb": 6.0,
        "pot_bb_live": 6.0,
        "ante_bb": 0.0,
        "effective_bb": 100.0,
        "hero_stack_start_bb": 100.0,
        "villain_stack_start_bb": 100.0,
        "hero_stack_bb": 97.0,
        "villain_stack_bb": 97.0,
        "hero_committed_bb": 0.0,
        "villain_committed_bb": 0.0,
        "stack_depth_bucket": "deep",
        "spr_bb": 16.0,
        "history": [],
        "legal_actions": [
            {"type": "check", "min_to_bb": None, "max_to_bb": None},
            {"type": "bet", "min_to_bb": 1.0, "max_to_bb": 97.0},
        ],
        "villain_profile": "unknown",
        "villain_stats": {"hands_played": 0},
        "bb_chips": 100,
        "payout_structure": None,
        "blind_level_label": "",
    }
    rendered = renderer.render("coach", "v3", variables)
    assert rendered.version == "v3"
    # v3-specific content: the prompt asks for a `strategy` field.
    assert "strategy" in rendered.rendered_prompt.lower()
    # hero_hole IS permitted in coach prompt (same contract as v2).
    assert "Ah Kh" in rendered.rendered_prompt
    # bb_chips is a backend sidecar — it must NOT leak into the rendered prompt.
    assert "bb_chips" not in rendered.rendered_prompt
    # And it round-trips on the variables dict for downstream consumers.
    assert rendered.variables["bb_chips"] == 100


def test_v3_renders_live_pot() -> None:
    """pot_bb_live = pot + hero_committed + villain_committed, in BB."""
    state = start_hand(effective_stack=10_000, bb=100, button="hero", hero_hole=("As", "Kd"))
    # Hero opens to 250, villain raises to 900 → live pot = 1150 chips = 11.5bb
    state = apply_action(state, Action(actor="hero", type="raise", to_amount=250))
    state = apply_action(state, Action(actor="villain", type="raise", to_amount=900))

    variables = state_to_coach_variables(
        state,
        villain_profile="unknown",
        villain_stats={"hands_played": 0},
        include_bb_chips=True,
    )
    assert variables["pot_bb_live"] == pytest.approx(11.5)

    renderer = PromptRenderer(REPO_ROOT / "prompts")
    rendered = renderer.render("coach", "v3", variables)
    assert "Pot (live, including this street): 11.5 bb" in rendered.rendered_prompt


def test_v3_renders_payout_structure_when_provided() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown",
        villain_stats={"hands_played": 0},
        include_bb_chips=True,
        payout_structure=[0.65, 0.35],
        blind_level_label="50/100 + 100 ante",
    )
    renderer = PromptRenderer(REPO_ROOT / "prompts")
    rendered = renderer.render("coach", "v3", variables)
    assert "Payout structure" in rendered.rendered_prompt
    assert "0.65" in rendered.rendered_prompt
    assert "50/100" in rendered.rendered_prompt


def test_v3_omits_payout_block_when_not_provided() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown",
        villain_stats={"hands_played": 0},
        include_bb_chips=True,
    )
    renderer = PromptRenderer(REPO_ROOT / "prompts")
    rendered = renderer.render("coach", "v3", variables)
    assert "Tournament context" not in rendered.rendered_prompt


def test_v3_renders_ante_block() -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        ante=50,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown",
        villain_stats={"hands_played": 0},
        include_bb_chips=True,
    )
    assert variables["ante_bb"] == pytest.approx(0.5)

    renderer = PromptRenderer(REPO_ROOT / "prompts")
    rendered = renderer.render("coach", "v3", variables)
    assert "Ante (BB posts): 0.5 bb" in rendered.rendered_prompt
