from __future__ import annotations

from pathlib import Path

import numpy as np

from poker_rta.capture.grab import crop_roi, load_image
from poker_rta.profile.model import ROI


def test_crop_roi_returns_expected_shape(fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    roi = ROI(x=572, y=560, width=60, height=80)
    crop = crop_roi(img, roi)
    assert crop.shape == (80, 60, 3)
    assert crop.dtype == np.uint8


def test_crop_roi_clips_to_image_bounds(fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    roi = ROI(x=img.shape[1] - 10, y=img.shape[0] - 10, width=50, height=50)
    crop = crop_roi(img, roi)
    assert crop.shape == (10, 10, 3)
