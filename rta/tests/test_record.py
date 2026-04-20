from __future__ import annotations

from pathlib import Path

import numpy as np

from poker_rta.record import SessionRecorder, replay_session


def test_record_and_replay(tmp_path: Path) -> None:
    rec = SessionRecorder(tmp_path)
    frame = (np.random.rand(10, 10, 3) * 255).astype(np.uint8)
    rec.record(frame)
    rec.record(frame)
    frames = list(replay_session(tmp_path))
    assert len(frames) == 2
    assert frames[0].shape == (10, 10, 3)
