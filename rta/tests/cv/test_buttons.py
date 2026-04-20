from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from poker_rta.cv.buttons import ButtonDetector


@pytest.fixture
def detector(tmp_path: Path) -> ButtonDetector:
    # Synthesize two tiny templates: "FOLD" and "CHECK"
    for label in ("fold", "check"):
        img = np.zeros((20, 60, 3), dtype=np.uint8)
        cv2.putText(img, label.upper(), (2, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imwrite(str(tmp_path / f"{label}.png"), img)
    return ButtonDetector({"fold": tmp_path / "fold.png", "check": tmp_path / "check.png"})


def test_detects_present_button(detector: ButtonDetector) -> None:
    img = np.zeros((30, 240, 3), dtype=np.uint8)
    cv2.putText(img, "FOLD", (2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    assert "fold" in detector.detect(img)
    assert "check" not in detector.detect(img)
