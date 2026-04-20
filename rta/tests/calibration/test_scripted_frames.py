"""Scripted-hand corpus loader tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from poker_rta.calibration.scripted_frames import (
    ScriptedFrame,
    load_scripted_corpus,
)

_CORPUS = Path(__file__).resolve().parents[1] / "fixtures/recordings/mock_script"


def test_mock_script_corpus_has_five_frames_and_truth_entries() -> None:
    """Plan-9 anchor: the mock_html test corpus ships exactly 5 entries
    so the Test-calibration modal always shows a full 5-row table."""
    gt = json.loads((_CORPUS / "ground_truth.json").read_text())
    assert len(gt) == 5
    frames = load_scripted_corpus(_CORPUS)
    assert len(frames) == 5
    for frame in frames:
        assert isinstance(frame, ScriptedFrame)
        assert frame.image is not None
        assert frame.description  # never empty
        # Ground-truth entries describe observable state, not a description.
        assert "description" not in frame.expected


def test_corpus_preserves_step_index_ordering() -> None:
    frames = load_scripted_corpus(_CORPUS)
    assert [f.step_index for f in frames] == [0, 1, 2, 3, 4]


def test_corpus_falls_back_to_first_frame_for_missing_indexed_images(
    tmp_path: Path,
) -> None:
    """Real multi-frame capture requires Playwright; until it lands the
    loader reuses 000000.png for any missing indexed frame."""
    import shutil

    target = tmp_path / "mock_script"
    target.mkdir()
    shutil.copy(_CORPUS / "000000.png", target / "000000.png")
    (target / "ground_truth.json").write_text(
        json.dumps(
            [
                {"description": "a", "pot_chips": 0},
                {"description": "b", "pot_chips": 100},
                {"description": "c", "pot_chips": 200},
            ]
        )
    )
    frames = load_scripted_corpus(target)
    assert len(frames) == 3
    # All three point at the only image, loaded fresh — not None.
    assert all(f.image is not None for f in frames)


def test_missing_ground_truth_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_scripted_corpus(tmp_path)


def test_format_validation_report_renders_pass_and_fail(tmp_path: Path) -> None:
    from poker_rta.calibration.scripted_frames import format_validation_report_html
    from poker_rta.calibration.validate import ValidationRow

    rows = [
        ValidationRow(step_index=0, description="preflop", passed=True, mismatches=[]),
        ValidationRow(
            step_index=1,
            description="flop villain X",
            passed=False,
            mismatches=["pot_chips: expected=600 observed=None"],
        ),
    ]
    html = format_validation_report_html(rows)
    assert "PASS" in html
    assert "FAIL" in html
    assert "#4a4" in html  # PASS green
    assert "#c33" in html  # FAIL red
    assert "pot_chips: expected=600 observed=None" in html
