"""Auto-capture missing card templates from the calibration preview.

Card templates are the scalar cost of onboarding a new poker client:
52 cards per deck, and a missing template means a dead classifier.
This module hands the user a `Save as …` affordance on any unmatched
card ROI so the template set grows organically while they calibrate.

Pure-data: the capture helper writes a PNG and appends to an audit
log. No Qt dependencies — tests synthesize a crop with numpy and
assert the classifier picks it up after `reload()`.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import cv2
import numpy as np

_RANK_CHARS = "23456789TJQKA"
_SUIT_CHARS = "cdhs"
_CODE_RE = re.compile(rf"^([{_RANK_CHARS}])([{_SUIT_CHARS}])$")

_LOG_FILENAME = ".capture_log.jsonl"


def is_valid_card_code(code: str) -> bool:
    """True iff `code` matches the canonical `{rank}{suit}` form.

    Examples: "As", "Td", "2c". Rejects "AS", "Tds", "10h", "1s",
    whitespace, or any non-card string. Guards the UI against typos
    that would otherwise produce a file like `Jr.png`.
    """
    return bool(_CODE_RE.match(code))


def capture_template(
    card_code: str,
    crop: np.ndarray,
    templates_dir: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Persist `crop` as a card template named `{card_code}.png`.

    Raises ValueError on invalid card codes or empty crops, and
    FileExistsError when the target already exists and `overwrite` is
    False. Writes an append-only audit line to `.capture_log.jsonl` in
    the same directory so new templates can be traced back to the
    moment they were added.
    """
    if not is_valid_card_code(card_code):
        raise ValueError(
            f"invalid card code {card_code!r} — expected {{rank}}{{suit}} like 'As', 'Td'"
        )
    if crop is None or crop.size == 0:
        raise ValueError("empty crop — cannot capture template")

    templates_dir.mkdir(parents=True, exist_ok=True)
    target = templates_dir / f"{card_code}.png"
    if target.exists() and not overwrite:
        raise FileExistsError(f"template already exists: {target}")

    if not cv2.imwrite(str(target), crop):
        raise RuntimeError(f"cv2.imwrite failed for {target}")

    _append_log(templates_dir, card_code, target, overwrite=overwrite)
    return target


def _append_log(
    templates_dir: Path,
    code: str,
    path: Path,
    *,
    overwrite: bool,
) -> None:
    log_path = templates_dir / _LOG_FILENAME
    entry = {
        "card_code": code,
        "path": str(path),
        "captured_at": time.time(),
        "overwrite": overwrite,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
