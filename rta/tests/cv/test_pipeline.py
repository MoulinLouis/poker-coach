from __future__ import annotations

from pathlib import Path

import pytest

from poker_rta.capture.grab import load_image
from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import FrameObservation, observe_frame
from poker_rta.profile import load_profile

_BUTTONS_DIR = Path(__file__).parents[2] / "templates" / "mock_html" / "buttons"
_BUTTON_TEMPLATES_PRESENT = (
    any(p.suffix == ".png" for p in _BUTTONS_DIR.iterdir())
    if _BUTTONS_DIR.exists()
    else False
)


@pytest.fixture
def profile_path() -> Path:
    return Path(__file__).parents[2] / "profiles" / "mock_html.yaml"


@pytest.mark.slow
@pytest.mark.skipif(
    not _BUTTON_TEMPLATES_PRESENT,
    reason="button templates are not committed (no build_mock_button_templates.py script yet)",
)
def test_observe_preflop_screenshot(profile_path: Path, fixtures_dir: Path) -> None:
    profile = load_profile(profile_path)
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    templates = Path(__file__).parents[2] / "templates" / "mock_html" / "cards"
    obs = observe_frame(img, profile, CardClassifier(templates))
    assert isinstance(obs, FrameObservation)
    assert obs.hero_cards == ("As", "Kd")
    assert obs.board == ()
    assert obs.pot_chips == 300
    assert obs.hero_stack_chips == 9850
    assert obs.villain_stack_chips == 9700
