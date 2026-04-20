from __future__ import annotations

from pathlib import Path

import pytest

from poker_rta.capture.grab import crop_roi, load_image
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.profile.model import ROI


@pytest.fixture
def classifier() -> CardClassifier:
    templates = Path(__file__).parents[2] / "templates" / "mock_html" / "cards"
    return CardClassifier(templates_dir=templates)


def test_classify_ace_of_spades(classifier: CardClassifier, fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    crop = crop_roi(img, ROI(x=572, y=560, width=60, height=80))
    assert classify_card(crop, classifier) == "As"


def test_classify_king_of_diamonds(classifier: CardClassifier, fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    crop = crop_roi(img, ROI(x=640, y=560, width=60, height=80))
    assert classify_card(crop, classifier) == "Kd"


def test_classify_unknown_returns_none(classifier: CardClassifier, fixtures_dir: Path) -> None:
    import numpy as np

    blank = np.zeros((80, 60, 3), dtype=np.uint8)
    assert classify_card(blank, classifier, min_score=0.85) is None
