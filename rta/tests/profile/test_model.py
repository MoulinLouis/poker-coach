from __future__ import annotations

import pytest
from pydantic import ValidationError

from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)


def test_roi_requires_positive_dimensions() -> None:
    with pytest.raises(ValidationError):
        ROI(x=0, y=0, width=0, height=10)
    with pytest.raises(ValidationError):
        ROI(x=0, y=0, width=10, height=-5)


def test_profile_requires_all_core_rois() -> None:
    with pytest.raises(ValidationError):
        PlatformProfile(
            name="broken",
            version="1.0",
            window=WindowSelector(title_contains="x"),
            rois={},  # missing hero_cards, board, pot, hero_stack, villain_stack
            card_templates_dir="cards",
            button_templates={},
            ocr=OCRPreprocess(),
        )


def test_profile_valid_minimal() -> None:
    profile = PlatformProfile(
        name="mock",
        version="1.0",
        window=WindowSelector(title_contains="Mock"),
        rois={
            "hero_card_1": ROI(x=0, y=0, width=60, height=80),
            "hero_card_2": ROI(x=60, y=0, width=60, height=80),
            "board_1": ROI(x=0, y=100, width=60, height=80),
            "board_2": ROI(x=60, y=100, width=60, height=80),
            "board_3": ROI(x=120, y=100, width=60, height=80),
            "board_4": ROI(x=180, y=100, width=60, height=80),
            "board_5": ROI(x=240, y=100, width=60, height=80),
            "pot": ROI(x=0, y=200, width=120, height=30),
            "hero_stack": ROI(x=0, y=300, width=120, height=30),
            "villain_stack": ROI(x=0, y=400, width=120, height=30),
            "hero_bet": ROI(x=0, y=250, width=120, height=30),
            "villain_bet": ROI(x=0, y=450, width=120, height=30),
            "button_marker": ROI(x=0, y=500, width=30, height=30),
            "hero_action_highlight": ROI(x=0, y=550, width=200, height=30),
        },
        card_templates_dir="cards",
        button_templates={"check": "buttons/check.png", "fold": "buttons/fold.png"},
        ocr=OCRPreprocess(grayscale=True, threshold=128),
    )
    assert profile.name == "mock"
    assert profile.rois["hero_card_1"].width == 60
