"""Detect which action buttons are present by matching small templates in the
action-bar ROI. Used both to confirm 'it's our turn' and to constrain
`legal_actions` inferred from the visible state.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ButtonDetector:
    def __init__(self, templates: dict[str, Path], min_score: float = 0.75) -> None:
        self._templates: dict[str, np.ndarray] = {}
        for label, path in templates.items():
            tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tpl is None:
                raise FileNotFoundError(f"button template missing: {path}")
            self._templates[label] = tpl
        self._min_score = min_score

    def detect(self, img: np.ndarray) -> set[str]:
        present: set[str] = set()
        for label, tpl in self._templates.items():
            if tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
                continue
            result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            if float(result.max()) >= self._min_score:
                present.add(label)
        return present
