"""State panel tests — structural API (not screenshot) based.

Pure-data tests hit `format_bb` / `classify_to_act` /
`rendered_cards_from_state` directly. Qt-smoke tests (gated by
RTA_QT_SMOKE) assert that the painted widget exposes the same
structural getters so the paint path stays coupled to observable state.
"""

from __future__ import annotations

import os

import pytest

from poker_rta.overlay.state_format import (
    classify_to_act,
    format_bb,
    rendered_cards_from_state,
)

# ── pure-data tests ──────────────────────────────────────────────────────────


def test_format_bb_rounds_to_one_decimal() -> None:
    assert format_bb(9700, 100) == 97.0
    assert format_bb(6033, 100) == 60.3
    assert format_bb(0, 100) == 0.0


def test_format_bb_guards_zero_bb() -> None:
    assert format_bb(9700, 0) == 0.0


def test_classify_to_act_accepts_known_seats() -> None:
    assert classify_to_act({"to_act": "hero"}) == "hero"
    assert classify_to_act({"to_act": "villain"}) == "villain"


def test_classify_to_act_rejects_garbage_or_missing() -> None:
    assert classify_to_act({"to_act": None}) is None
    assert classify_to_act({}) is None
    assert classify_to_act(None) is None
    assert classify_to_act({"to_act": "bot"}) is None


def test_rendered_cards_concatenates_hero_then_board() -> None:
    state = {"hero_hole": ["As", "Kd"], "board": ["Ah", "7c", "2d"]}
    assert rendered_cards_from_state(state) == ("As", "Kd", "Ah", "7c", "2d")


def test_rendered_cards_empty_for_no_state() -> None:
    assert rendered_cards_from_state(None) == ()
    assert rendered_cards_from_state({}) == ()


# ── Qt-smoke tests ───────────────────────────────────────────────────────────


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_state_panel_exposes_structural_getters() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.state_panel import StateMirrorPanel

    app = QApplication.instance() or QApplication([])

    state = {
        "bb": 100,
        "hero_hole": ["As", "Kd"],
        "board": ["Ah", "7c", "2d"],
        "pot": 600,
        "stacks": {"hero": 9700, "villain": 9400},
        "committed": {"hero": 0, "villain": 0},
        "to_act": "hero",
        "street": "flop",
    }
    panel = StateMirrorPanel()
    panel.update_state(state)
    assert panel.rendered_cards() == ("As", "Kd", "Ah", "7c", "2d")
    assert panel.rendered_pot_bb() == 6.0
    assert panel.rendered_to_act() == "hero"
    # Board slots always 5 wide; unrevealed slots are empty strings.
    assert panel.rendered_board_slots() == ("Ah", "7c", "2d", "", "")

    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_state_panel_none_clears() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.state_panel import StateMirrorPanel

    app = QApplication.instance() or QApplication([])
    panel = StateMirrorPanel()
    panel.update_state(None)
    assert panel.rendered_cards() == ()
    assert panel.rendered_pot_bb() is None
    assert panel.rendered_to_act() is None
    assert panel.current_text().startswith("waiting")
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_state_panel_board_slots_pad_to_five_preflop() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.state_panel import StateMirrorPanel

    app = QApplication.instance() or QApplication([])
    panel = StateMirrorPanel()
    panel.update_state(
        {
            "bb": 100,
            "hero_hole": ["As", "Kd"],
            "board": [],
            "pot": 0,
            "stacks": {"hero": 10000, "villain": 10000},
            "committed": {"hero": 50, "villain": 100},
            "to_act": "hero",
            "street": "preflop",
        }
    )
    assert panel.rendered_board_slots() == ("", "", "", "", "")
    app.quit()
