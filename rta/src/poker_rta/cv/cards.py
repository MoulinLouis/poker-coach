"""Card classifier via normalized cross-correlation template matching.

For digital poker clients with a stable card style, template matching is:
- deterministic (no training required)
- explainable for the research paper
- ~100% accurate when templates match the client's rendering
If a client changes its card art, we regenerate the templates. Robustness to
style changes is out of scope for MVP; note as future work in the paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

CardCode = str  # e.g., "As", "Kd", "Th"


@dataclass
class CardClassifier:
    templates_dir: Path
    _templates: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._load_from_disk()
        if not self._templates:
            raise FileNotFoundError(f"no card templates found in {self.templates_dir}")

    def _load_from_disk(self) -> None:
        self._templates.clear()
        for path in self.templates_dir.glob("*.png"):
            tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            self._templates[path.stem] = tpl

    def reload(self) -> None:
        """Re-read templates from disk so a freshly captured template
        is picked up without reconstructing the classifier. Raises
        FileNotFoundError if the directory becomes empty."""
        self._load_from_disk()
        if not self._templates:
            raise FileNotFoundError(f"no card templates found in {self.templates_dir}")

    def match(self, img: np.ndarray) -> tuple[CardCode, float]:
        best_code = ""
        best_score = -1.0
        for code, tpl in self._templates.items():
            if tpl.shape != img.shape:
                resized = cv2.resize(tpl, (img.shape[1], img.shape[0]))
            else:
                resized = tpl
            result = cv2.matchTemplate(img, resized, cv2.TM_CCOEFF_NORMED)
            score = float(result.max())
            if score > best_score:
                best_score, best_code = score, code
        return best_code, best_score


def classify_card(
    roi_img: np.ndarray,
    classifier: CardClassifier,
    min_score: float = 0.85,
) -> CardCode | None:
    """Classify one card-sized ROI. Returns the card code or None if no
    template matches above the score threshold (e.g., empty slot or card back)."""

    code, score = classifier.match(roi_img)
    return code if score >= min_score else None
