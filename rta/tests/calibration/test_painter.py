from __future__ import annotations

from poker_rta.calibration.painter import CalibrationDoc, emit_profile


def test_emit_profile_uses_clicked_rois() -> None:
    doc = CalibrationDoc(
        name="friend",
        version="1.0",
        window_title="Friend App",
        card_templates_dir="templates/friend/cards",
        button_templates={},
        rois={
            "hero_card_1": (10, 10, 60, 80),
            "hero_card_2": (70, 10, 60, 80),
            "board_1": (10, 100, 60, 80),
            "board_2": (70, 100, 60, 80),
            "board_3": (130, 100, 60, 80),
            "board_4": (190, 100, 60, 80),
            "board_5": (250, 100, 60, 80),
            "pot": (10, 200, 120, 30),
            "hero_stack": (10, 300, 120, 30),
            "villain_stack": (10, 400, 120, 30),
            "hero_bet": (10, 250, 120, 30),
            "villain_bet": (10, 450, 120, 30),
            "button_marker": (10, 500, 30, 30),
            "hero_action_highlight": (10, 550, 200, 30),
        },
    )
    profile = emit_profile(doc)
    assert profile.name == "friend"
    assert profile.rois["hero_card_1"].x == 10
    assert profile.window.title_contains == "Friend App"
