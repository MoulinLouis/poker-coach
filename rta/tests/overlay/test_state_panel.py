from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_state_panel_renders() -> None:
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
    txt = panel.current_text()
    assert "AsKd" in txt
    assert "Ah 7c 2d" in txt
    assert "pot 6.0bb" in txt
    assert "hero 97.0bb" in txt

    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_state_panel_none_clears() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.state_panel import StateMirrorPanel

    app = QApplication.instance() or QApplication([])
    panel = StateMirrorPanel()
    panel.update_state(None)
    assert panel.current_text() == "—"
    app.quit()
