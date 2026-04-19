"""Live per-ROI preview: crop an image by ROI coordinates and run an
interpreter to produce a human-readable label + confidence score.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ROIPreview:
    name: str
    shape: tuple[int, int, int]  # (h, w, channels)
    interpretation: str
    confidence: float


def extract_preview(
    name: str,
    image: np.ndarray,
    roi: tuple[int, int, int, int],  # (x, y, w, h)
    interpret: Callable[[np.ndarray], tuple[str, float]],
) -> ROIPreview:
    x, y, w, h = roi
    crop = image[y : y + h, x : x + w]
    text, confidence = interpret(crop)
    return ROIPreview(name=name, shape=crop.shape, interpretation=text, confidence=confidence)
