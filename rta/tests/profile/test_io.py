from __future__ import annotations

from pathlib import Path

from poker_rta.profile import PlatformProfile, load_profile, save_profile
from poker_rta.profile.model import ROI, OCRPreprocess, WindowSelector


def _minimal_profile() -> PlatformProfile:
    rois = {
        name: ROI(x=i, y=i, width=60, height=80)
        for i, name in enumerate(
            [
                "hero_card_1",
                "hero_card_2",
                "board_1",
                "board_2",
                "board_3",
                "board_4",
                "board_5",
                "pot",
                "hero_stack",
                "villain_stack",
                "hero_bet",
                "villain_bet",
                "button_marker",
                "hero_action_highlight",
            ],
            start=1,
        )
    }
    return PlatformProfile(
        name="test",
        version="1.0",
        window=WindowSelector(title_contains="Test"),
        rois=rois,
        card_templates_dir="cards",
        button_templates={"check": "buttons/check.png"},
        ocr=OCRPreprocess(),
    )


def test_round_trip(tmp_path: Path) -> None:
    original = _minimal_profile()
    target = tmp_path / "profile.yaml"
    save_profile(original, target)
    loaded = load_profile(target)
    assert loaded == original


def test_load_rejects_missing_roi(tmp_path: Path) -> None:
    import pytest
    from pydantic import ValidationError

    target = tmp_path / "broken.yaml"
    target.write_text(
        "name: broken\nversion: '1.0'\nwindow: {title_contains: x}\n"
        "rois:\n  hero_card_1: {x: 0, y: 0, width: 10, height: 10}\n"
        "card_templates_dir: cards\nbutton_templates: {}\nocr: {}\n"
    )
    with pytest.raises(ValidationError):
        load_profile(target)
