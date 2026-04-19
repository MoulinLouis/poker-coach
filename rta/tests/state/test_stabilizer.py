from __future__ import annotations

from poker_rta.state.stabilizer import FrameStabilizer


def test_three_identical_frames_emits_on_third(obs):
    """3 identical frames → 3rd returns obs; 1st & 2nd return None."""
    stabilizer = FrameStabilizer(stable_frames=3)
    frame = obs()

    assert stabilizer.ingest(frame) is None  # 1st
    assert stabilizer.ingest(frame) is None  # 2nd
    result = stabilizer.ingest(frame)  # 3rd
    assert result is frame


def test_anomalous_frame_mid_stream_resets_counter(obs):
    """Anomalous frame mid-stream resets counter."""
    stabilizer = FrameStabilizer(stable_frames=3)
    frame_a = obs(pot_chips=150)
    frame_b = obs(pot_chips=300)  # different frame

    assert stabilizer.ingest(frame_a) is None  # count=1
    assert stabilizer.ingest(frame_a) is None  # count=2
    assert stabilizer.ingest(frame_b) is None  # reset, count=1 for frame_b
    assert stabilizer.ingest(frame_a) is None  # reset again, count=1 for frame_a
    assert stabilizer.ingest(frame_a) is None  # count=2
    result = stabilizer.ingest(frame_a)  # count=3, should emit
    assert result is frame_a


def test_no_double_emit_same_obs(obs):
    """Once emitted, same obs repeated → None (no double-emit)."""
    stabilizer = FrameStabilizer(stable_frames=3)
    frame = obs()

    # Emit once
    stabilizer.ingest(frame)
    stabilizer.ingest(frame)
    assert stabilizer.ingest(frame) is frame

    # Repeating same obs should not re-emit
    assert stabilizer.ingest(frame) is None
    assert stabilizer.ingest(frame) is None
    assert stabilizer.ingest(frame) is None
