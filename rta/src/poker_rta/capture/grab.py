"""Screen capture primitives.

`grab_window` uses mss to pull a rectangular region from the live display.
`load_image` + `crop_roi` are the test-friendly counterparts used by offline
tests and the replay harness.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import mss
import numpy as np

from poker_rta.profile.model import ROI, WindowSelector


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"cannot read image: {path}")
    return img  # BGR


def crop_roi(img: np.ndarray, roi: ROI) -> np.ndarray:
    h, w = img.shape[:2]
    x2 = min(roi.x + roi.width, w)
    y2 = min(roi.y + roi.height, h)
    return img[roi.y : y2, roi.x : x2]


def grab_bbox(bbox: ROI) -> np.ndarray:
    """Grab a rectangular region from the primary display (BGR)."""
    with mss.mss() as sct:
        region = {"left": bbox.x, "top": bbox.y, "width": bbox.width, "height": bbox.height}
        raw = np.asarray(sct.grab(region))  # BGRA
    return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)


def grab_window(selector: WindowSelector) -> np.ndarray:
    """Grab a region specified by a WindowSelector.

    When `bbox` is set, captures that region directly. When `title_contains` is
    set, the OS-specific window-lookup has to be plugged in by the caller; for
    initial milestones we use `bbox` only and leave title-based lookup as a
    platform-adapter extension point.
    """
    if selector.bbox is not None:
        return grab_bbox(selector.bbox)
    from poker_rta.capture.window import resolve_title_to_bbox

    assert selector.title_contains is not None  # mutually exclusive invariant
    bbox = resolve_title_to_bbox(selector.title_contains)
    if bbox is None:
        raise LookupError(f"window with title containing {selector.title_contains!r} not found")
    return grab_bbox(bbox)
