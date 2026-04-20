import numpy as np

from poker_rta.calibration.preview import extract_preview


def test_extract_preview_crops_and_passes_through():
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    result = extract_preview(
        "pot",
        img,
        (10, 20, 50, 30),
        interpret=lambda crop: ("hello", 0.87),
    )
    assert result.shape == (30, 50, 3)
    assert result.interpretation == "hello"
    assert result.confidence == 0.87
    assert result.name == "pot"
