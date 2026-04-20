"""Template auto-capture tests.

End-to-end: synthesize a card crop with numpy, call
`capture_template`, assert the file exists and — after
`classifier.reload()` — the classifier matches that exact crop back to
the captured code.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from poker_rta.calibration.template_capture import (
    capture_template,
    is_valid_card_code,
)
from poker_rta.cv.cards import CardClassifier, classify_card


@pytest.mark.parametrize("code", ["As", "Kd", "Tc", "2h", "9s"])
def test_is_valid_card_code_accepts_canonical_codes(code: str) -> None:
    assert is_valid_card_code(code) is True


@pytest.mark.parametrize(
    "code",
    ["AS", "as", "1s", "10h", "Tds", "", "As ", " As", "Xh", "A", "7"],
)
def test_is_valid_card_code_rejects_malformed(code: str) -> None:
    assert is_valid_card_code(code) is False


def _fake_crop(seed: int, shape: tuple[int, int, int] = (40, 30, 3)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=shape, dtype=np.uint8)


def test_capture_template_writes_png_and_log(tmp_path: Path) -> None:
    crop = _fake_crop(seed=1)
    target = capture_template("As", crop, tmp_path)
    assert target.exists()
    assert target.name == "As.png"

    log_path = tmp_path / ".capture_log.jsonl"
    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["card_code"] == "As"
    assert entries[0]["path"] == str(target)
    assert entries[0]["overwrite"] is False


def test_capture_template_refuses_invalid_card_code(tmp_path: Path) -> None:
    crop = _fake_crop(seed=1)
    with pytest.raises(ValueError, match="invalid card code"):
        capture_template("Jr", crop, tmp_path)
    with pytest.raises(ValueError, match="invalid card code"):
        capture_template("10s", crop, tmp_path)


def test_capture_template_refuses_empty_crop(tmp_path: Path) -> None:
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="empty crop"):
        capture_template("As", empty, tmp_path)


def test_capture_template_refuses_overwrite_by_default(tmp_path: Path) -> None:
    crop = _fake_crop(seed=1)
    capture_template("As", crop, tmp_path)
    with pytest.raises(FileExistsError):
        capture_template("As", crop, tmp_path)


def test_capture_template_overwrite_replaces_existing(tmp_path: Path) -> None:
    first = _fake_crop(seed=1)
    second = _fake_crop(seed=2)
    capture_template("As", first, tmp_path)
    capture_template("As", second, tmp_path, overwrite=True)
    stored = cv2.imread(str(tmp_path / "As.png"), cv2.IMREAD_COLOR)
    assert np.array_equal(stored, second)


def test_classifier_reload_picks_up_newly_captured_template(tmp_path: Path) -> None:
    """The whole point of Plan 10: save a template, call reload(),
    next preview pass recognizes that exact crop."""
    # Seed the directory with ONE starter template so CardClassifier
    # construction doesn't raise on an empty directory.
    seed = _fake_crop(seed=99)
    cv2.imwrite(str(tmp_path / "2c.png"), seed)
    classifier = CardClassifier(templates_dir=tmp_path)

    # Capture a new template for the ace of spades.
    ace_crop = _fake_crop(seed=42)
    capture_template("As", ace_crop, tmp_path)

    # Before reload the classifier is blind to "As".
    code, _ = classifier.match(ace_crop)
    assert code != "As"

    classifier.reload()
    assert classify_card(ace_crop, classifier, min_score=0.99) == "As"


def test_capture_template_log_appends_not_overwrites(tmp_path: Path) -> None:
    capture_template("As", _fake_crop(seed=1), tmp_path)
    capture_template("Kd", _fake_crop(seed=2), tmp_path)
    capture_template("Qc", _fake_crop(seed=3), tmp_path)
    log_path = tmp_path / ".capture_log.jsonl"
    lines = log_path.read_text().splitlines()
    assert [json.loads(line)["card_code"] for line in lines] == ["As", "Kd", "Qc"]
