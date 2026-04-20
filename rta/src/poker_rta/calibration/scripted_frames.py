"""Scripted-hand corpus loader.

A corpus is a directory of captured frames `NNNNNN.png` plus a
`ground_truth.json` listing the expected observation per frame.
Loading is decoupled from the "Test calibration" GUI modal so the
scripted-hand pipeline can be driven from a unit test too.

Today the mock_html corpus ships one screenshot reused across all 5
script entries (real multi-frame capture needs Playwright; see
`scripts/capture_mock_screenshot.py`). The loader tolerates missing
indexed frames by falling back to `000000.png`, so the same code path
works once real captures land.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from poker_rta.calibration.validate import ValidationRow, validate_step
from poker_rta.capture.grab import load_image
from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import observe_frame
from poker_rta.profile.model import PlatformProfile


@dataclass(frozen=True)
class ScriptedFrame:
    """One step in a scripted hand."""

    step_index: int
    description: str
    image: np.ndarray
    expected: dict[str, Any]


def load_scripted_corpus(corpus_dir: Path) -> list[ScriptedFrame]:
    """Load all scripted frames from a corpus directory.

    Raises FileNotFoundError if the corpus is absent or lacks any
    image. Malformed ground_truth.json propagates as ValueError via
    json.loads.
    """
    ground_truth_path = corpus_dir / "ground_truth.json"
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"missing {ground_truth_path}")
    raw = json.loads(ground_truth_path.read_text())
    if not isinstance(raw, list):
        raise ValueError("ground_truth.json must be a JSON list")

    fallback = corpus_dir / "000000.png"
    frames: list[ScriptedFrame] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"ground_truth[{i}] must be an object")
        entry = dict(entry)  # copy so we can pop description without mutating input
        indexed = corpus_dir / f"{i:06d}.png"
        image_path = indexed if indexed.exists() else fallback
        if not image_path.exists():
            raise FileNotFoundError(f"no image available for step {i}")
        image = load_image(image_path)
        description = str(entry.pop("description", f"step {i}"))
        frames.append(
            ScriptedFrame(
                step_index=i,
                description=description,
                image=image,
                expected=entry,
            )
        )
    return frames


def _format_validation_row_html(row: ValidationRow) -> str:
    """Render one ValidationRow as a single HTML line. PASS cells
    green, FAIL cells red; colors inline so the modal doesn't need a
    stylesheet."""
    status = "PASS" if row.passed else "FAIL"
    color = "#4a4" if row.passed else "#c33"
    detail = "&empty;" if row.passed else "; ".join(row.mismatches)
    return (
        f"<tr><td>[{row.step_index + 1}]</td>"
        f"<td>{row.description}</td>"
        f'<td style="color:{color}; font-weight:bold;">{status}</td>'
        f"<td>{detail}</td></tr>"
    )


def format_validation_report_html(rows: list[ValidationRow]) -> str:
    """Full HTML table for the Test-calibration modal. Qt-free so the
    formatting can be unit-tested without importing PyQt6."""
    lines = [_format_validation_row_html(r) for r in rows]
    header = "<tr><th>#</th><th>description</th><th>result</th><th>detail</th></tr>"
    return f'<table cellpadding="4" cellspacing="0" border="0">{header}{"".join(lines)}</table>'


def run_scripted_validation(
    frames: list[ScriptedFrame],
    profile: PlatformProfile,
    classifier: CardClassifier,
) -> list[ValidationRow]:
    """Observe each frame with the current profile + classifier and
    compare against ground truth. Returns one `ValidationRow` per
    frame; caller renders (GUI table, CLI summary, whatever)."""
    rows: list[ValidationRow] = []
    for frame in frames:
        obs = observe_frame(frame.image, profile, classifier)
        observed = {
            "hero_cards": list(obs.hero_cards) if obs.hero_cards else None,
            "board": list(obs.board),
            "pot_chips": obs.pot_chips,
            "hero_stack_chips": obs.hero_stack_chips,
            "villain_stack_chips": obs.villain_stack_chips,
        }
        rows.append(
            validate_step(
                step_index=frame.step_index,
                description=frame.description,
                expected=frame.expected,
                observed=observed,
            )
        )
    return rows
