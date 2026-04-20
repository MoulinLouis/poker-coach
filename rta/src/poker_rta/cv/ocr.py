"""OCR for chip amounts (stacks, pot, bets).

EasyOCR is the default engine — works cross-platform without system deps, good
digit accuracy. Preprocessing per-profile (threshold, invert, scale) lets us
adapt to dark/light text and low-DPI captures.
"""

from __future__ import annotations

import re
from functools import lru_cache

import cv2
import numpy as np

from poker_rta.profile.model import OCRPreprocess

_NUM_RE = re.compile(r"[-+]?[\d,]+")


def parse_chip_amount(raw: str) -> int | None:
    """Parse '$1,234' / '1234' / '1,234 bb' → 1234. None if no digits present."""
    m = _NUM_RE.search(raw)
    if m is None:
        return None
    digits = m.group(0).replace(",", "")
    try:
        return int(digits)
    except ValueError:
        return None


def _preprocess(img: np.ndarray, cfg: OCRPreprocess) -> np.ndarray:
    out = img
    if cfg.grayscale and out.ndim == 3:
        out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    if cfg.threshold is not None:
        _, out = cv2.threshold(out, cfg.threshold, 255, cv2.THRESH_BINARY)
    if cfg.invert:
        out = cv2.bitwise_not(out)
    if cfg.scale != 1.0:
        out = cv2.resize(out, None, fx=cfg.scale, fy=cfg.scale, interpolation=cv2.INTER_CUBIC)
    return out


@lru_cache(maxsize=1)
def _get_easyocr_reader() -> object:
    import easyocr  # lazy import — model download on first call

    return easyocr.Reader(["en"], gpu=False, verbose=False)


class NumberReader:
    def __init__(self, preprocess: OCRPreprocess) -> None:
        self._pp = preprocess

    def read(self, img: np.ndarray) -> int | None:
        processed = _preprocess(img, self._pp)
        reader = _get_easyocr_reader()
        results = reader.readtext(processed, allowlist="0123456789,$ ", detail=0)  # type: ignore[attr-defined]
        for text in results:
            val = parse_chip_amount(text)
            if val is not None:
                return val
        return None
