"""Record + replay frames for offline debugging, paper reproducibility, and
deterministic state-tracker tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SessionRecorder:
    root: Path
    _idx: int = field(default=0)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, frame: np.ndarray) -> Path:
        path = self.root / f"{self._idx:06d}.png"
        cv2.imwrite(str(path), frame)
        self._idx += 1
        return path


def replay_session(root: Path) -> Iterator[np.ndarray]:
    for p in sorted(root.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is not None:
            yield img
