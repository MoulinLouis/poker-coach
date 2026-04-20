from __future__ import annotations

from dataclasses import dataclass, field

from poker_rta.cv.pipeline import FrameObservation


@dataclass
class FrameStabilizer:
    stable_frames: int = 3
    _candidate: FrameObservation | None = field(default=None)
    _count: int = field(default=0)
    _last_emitted: FrameObservation | None = field(default=None)

    def ingest(self, obs: FrameObservation) -> FrameObservation | None:
        if obs != self._candidate:
            self._candidate, self._count = obs, 1
            return None
        self._count += 1
        if self._count < self.stable_frames or obs == self._last_emitted:
            return None
        self._last_emitted = obs
        return obs
